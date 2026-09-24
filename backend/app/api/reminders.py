import secrets
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.i18n import t
from app.models import User
from app.notify import DeliveryError, EmailSender, Telegram, email_sender, telegram, telegram_username
from app.reminders import Due, due_for, message

router = APIRouter(prefix="/reminders", tags=["reminders"])


def get_email() -> EmailSender | None:
    return email_sender()


def get_telegram() -> Telegram | None:
    return telegram()


class ReminderSettings(BaseModel):
    email_available: bool
    email_enabled: bool
    telegram_available: bool
    telegram_linked: bool
    days_before: int


class ReminderUpdate(BaseModel):
    email_enabled: bool
    days_before: int = Field(ge=0, le=14)


class TelegramLink(BaseModel):
    url: str


class TestResult(BaseModel):
    sent: list[str]
    failed: list[str]


def current(user: User, email: EmailSender | None, tg: Telegram | None) -> ReminderSettings:
    return ReminderSettings(email_available=email is not None, email_enabled=user.reminder_email,
                            telegram_available=tg is not None, telegram_linked=bool(user.telegram_chat_id),
                            days_before=user.reminder_days)


@router.get("", response_model=ReminderSettings)
def read_settings(user: User = Depends(get_current_user), email=Depends(get_email), tg=Depends(get_telegram)):
    return current(user, email, tg)


@router.put("", response_model=ReminderSettings)
def update_settings(payload: ReminderUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db),
                    email=Depends(get_email), tg=Depends(get_telegram)):
    user.reminder_email = payload.email_enabled
    user.reminder_days = payload.days_before
    db.commit()
    return current(user, email, tg)


@router.post("/telegram", response_model=TelegramLink)
def start_telegram_link(user: User = Depends(get_current_user), db: Session = Depends(get_db), tg=Depends(get_telegram)):
    """A t.me link that opens the bot with a one-time code; the reminder loop links the chat when it sees it."""
    username = telegram_username(settings.telegram_bot_token) if tg else None
    if not username:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Telegram reminders are not set up")
    user.telegram_link_code = secrets.token_urlsafe(12)
    db.commit()
    return TelegramLink(url=f"https://t.me/{username}?start={user.telegram_link_code}")


@router.delete("/telegram", status_code=status.HTTP_204_NO_CONTENT)
def unlink_telegram(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.telegram_chat_id = user.telegram_link_code = None
    db.commit()


@router.post("/test", response_model=TestResult)
def send_test(user: User = Depends(get_current_user), db: Session = Depends(get_db),
              email=Depends(get_email), tg=Depends(get_telegram)):
    """Send what a reminder would say right now (upcoming deadlines of the first company), to every channel on."""
    lang = user.language or "ka"
    subject, body = t("reminder.test_subject", lang), t("reminder.test_body", lang)
    for company in user.companies:
        items = due_for(user, company, db, date.today())
        if items:
            subject, body = message(Due(user, company, items), lang)
            break
    sent, failed = [], []
    for channel, on in (("email", email and user.reminder_email), ("telegram", tg and user.telegram_chat_id)):
        if not on:
            continue
        try:
            if channel == "email":
                email.send(user.email, subject, body)
            else:
                tg.send(user.telegram_chat_id, f"{subject}\n\n{body}")
            sent.append(channel)
        except DeliveryError:
            failed.append(channel)
    return TestResult(sent=sent, failed=failed)
