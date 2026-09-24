import hashlib
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import ratelimit
from app.auth import as_utc, end_session, get_current_user, hash_password, start_session, verify_login
from app.config import settings
from app.database import get_db
from app.i18n import Language, t
from app.models import AuthSession, PasswordReset, User
from app.notify import DeliveryError, EmailSender, get_email

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not EMAIL.match(value):
        raise ValueError("Enter a valid email address")
    return value


class RegisterRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    language: Language | None = None

    _email = field_validator("email")(normalize_email)


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=128)

    _email = field_validator("email")(lambda v: v.strip().lower())


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    language: Language | None = None
    is_reviewer: bool = False


class UserUpdate(BaseModel):
    language: Language


class ResetRequest(BaseModel):
    email: str = Field(max_length=320)
    language: Language | None = None

    _email = field_validator("email")(lambda v: v.strip().lower())


class ResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=128)
    password: str = Field(min_length=8, max_length=128)


class AuthFeatures(BaseModel):
    password_reset: bool


RESET_HOURS = 1
TOO_MANY = "Too many attempts. Please wait a few minutes and try again."


def client_ip(request: Request) -> str:
    # Behind the production proxy uvicorn runs with --proxy-headers, so this is the real client address.
    return request.client.host if request.client else "unknown"


def limit(*checks: tuple[ratelimit.RateLimiter, str]) -> None:
    if any(limiter.blocked(key) for limiter, key in checks):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY)


@router.get("/features", response_model=AuthFeatures)
def features(email: EmailSender | None = Depends(get_email)):
    return AuthFeatures(password_reset=email is not None)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    limit((ratelimit.REGISTER_BY_IP, ip))
    ratelimit.REGISTER_BY_IP.hit(ip)
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=payload.email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password),
                language=payload.language)
    db.add(user)
    db.commit()
    start_session(db, user, response)
    return user


@router.post("/login", response_model=UserRead)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    limit((ratelimit.LOGIN_BY_EMAIL, payload.email), (ratelimit.LOGIN_BY_IP, ip))
    user = verify_login(db, payload.email, payload.password)
    if user is None:
        ratelimit.LOGIN_BY_EMAIL.hit(payload.email)
        ratelimit.LOGIN_BY_IP.hit(ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    ratelimit.LOGIN_BY_EMAIL.clear(payload.email)
    start_session(db, user, response)
    return user


@router.post("/password-reset", status_code=status.HTTP_202_ACCEPTED)
def request_reset(payload: ResetRequest, request: Request, db: Session = Depends(get_db),
                  email: EmailSender | None = Depends(get_email)):
    """Email a one-time link. The answer is the same whether or not the account exists."""
    ip = client_ip(request)
    limit((ratelimit.RESET_BY_IP, ip), (ratelimit.RESET_BY_EMAIL, payload.email))
    ratelimit.RESET_BY_IP.hit(ip)
    ratelimit.RESET_BY_EMAIL.hit(payload.email)
    if email is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Password reset by email is not set up")
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is not None:
        token = secrets.token_urlsafe(32)
        db.add(PasswordReset(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                             expires_at=datetime.now(UTC) + timedelta(hours=RESET_HOURS)))
        db.commit()
        lang = payload.language or user.language or "ka"
        link = f"{settings.public_url.rstrip('/')}/#reset={token}"
        try:
            email.send(user.email, t("reset.subject", lang),
                       t("reset.body", lang, name=user.full_name, link=link, hours=RESET_HOURS))
        except DeliveryError:
            log.warning("Password reset email to %s failed", user.email)
    return {"status": "accepted"}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_reset(payload: ResetConfirm, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    limit((ratelimit.LOGIN_BY_IP, ip))
    reset = db.get(PasswordReset, hashlib.sha256(payload.token.encode()).hexdigest())
    if reset is None or as_utc(reset.expires_at) < datetime.now(UTC):
        ratelimit.LOGIN_BY_IP.hit(ip)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired")
    user = db.get(User, reset.user_id)
    user.password_hash = hash_password(payload.password)
    # A reset signs out every device and voids any other outstanding links.
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    db.commit()
    ratelimit.LOGIN_BY_EMAIL.clear(user.email)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    end_session(db, request, response)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user


class DeleteAccount(BaseModel):
    password: str = Field(max_length=128)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(payload: DeleteAccount, request: Request, response: Response, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """Delete the account and everything under it (companies, records, conversations). Needs the password."""
    ip = client_ip(request)
    limit((ratelimit.LOGIN_BY_EMAIL, user.email), (ratelimit.LOGIN_BY_IP, ip))
    if verify_login(db, user.email, payload.password) is None:
        ratelimit.LOGIN_BY_EMAIL.hit(user.email)
        ratelimit.LOGIN_BY_IP.hit(ip)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wrong password")
    db.delete(user)
    db.commit()
    response.delete_cookie("session")


@router.patch("/me", response_model=UserRead)
def update_me(payload: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.language = payload.language
    db.commit()
    return user
