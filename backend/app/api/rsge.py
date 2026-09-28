from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crypto
from app.api.companies import get_company
from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Company, CompanyRS
from app.rsge import TIN_PATTERN, RSAuthError, RSClient, RSError, Taxpayer

router = APIRouter(prefix="/rs", tags=["rs.ge"], dependencies=[Depends(get_current_user)])


class TaxpayerRead(BaseModel):
    tin: str
    name: str
    vat_payer: bool
    checked_at: datetime
    source: str = "rs.ge"


class RSStatus(BaseModel):
    configured: bool


def get_rs_client() -> RSClient | None:
    if not (settings.rs_service_user and settings.rs_service_password):
        return None
    return RSClient(settings.rs_url, settings.rs_service_user, settings.rs_service_password)


@router.get("/status", response_model=RSStatus)
def rs_status(rs: RSClient | None = Depends(get_rs_client)):
    return RSStatus(configured=rs is not None)


@router.get("/taxpayers/{tin}", response_model=TaxpayerRead)
def lookup_taxpayer(tin: str, rs: RSClient | None = Depends(get_rs_client)):
    tin = tin.strip()
    if not TIN_PATTERN.match(tin):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter a 9- or 11-digit code")
    if rs is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "RS.ge lookup is not set up")
    try:
        taxpayer = rs.lookup(tin)
    except RSAuthError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "RS.ge rejected the service user")
    except RSError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "RS.ge is not responding")
    if taxpayer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No taxpayer with this code on RS.ge")
    return TaxpayerRead(tin=taxpayer.tin, name=taxpayer.name, vat_payer=taxpayer.vat_payer,
                        checked_at=datetime.now(timezone.utc))


# --- a company's own RS.ge connection ---

company_router = APIRouter(prefix="/companies/{company_id}/rs", tags=["rs.ge"])

RSFactory = Callable[[str, str], RSClient]


def get_rs_factory() -> RSFactory:
    """Builds a client for one service user; tests override it and never call RS."""
    return lambda user, password: RSClient(settings.rs_url, user, password)


class RSConnectIn(BaseModel):
    service_user: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class RSConnection(BaseModel):
    available: bool  # credentials can be stored (CREDENTIALS_KEY set)
    connected: bool
    service_user: str | None = None
    status: Literal["ok", "rejected", "unreachable"] | None = None
    registered_name: str | None = None
    vat_payer: bool | None = None
    checked_at: datetime | None = None


def connection_view(row: CompanyRS | None) -> RSConnection:
    available = crypto.cipher() is not None
    if row is None:
        return RSConnection(available=available, connected=False)
    return RSConnection(available=available, connected=True, service_user=row.service_user, status=row.status,
                        registered_name=row.registered_name, vat_payer=row.vat_payer, checked_at=row.checked_at)


def company_connection(company: Company, db: Session) -> CompanyRS | None:
    return db.scalar(select(CompanyRS).where(CompanyRS.company_id == company.id))


def check_company(rs: RSClient, company: Company) -> tuple[str, Taxpayer | None]:
    """("ok", taxpayer) or ("rejected" | "unreachable", None); a missing taxpayer is an error the caller reports."""
    try:
        taxpayer = rs.lookup(company.tax_id)
    except RSAuthError:
        return "rejected", None
    except RSError:
        return "unreachable", None
    if taxpayer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "RS.ge has no taxpayer with this company's tax ID")
    return "ok", taxpayer


@company_router.get("", response_model=RSConnection)
def read_connection(company: Company = Depends(get_company), db: Session = Depends(get_db)):
    return connection_view(company_connection(company, db))


@company_router.put("", response_model=RSConnection)
def connect(payload: RSConnectIn, company: Company = Depends(get_company), db: Session = Depends(get_db),
            factory: RSFactory = Depends(get_rs_factory)):
    """Checks the service user against RS.ge with the company's own tax ID; stores it (encrypted) only if RS accepts it."""
    if crypto.cipher() is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Connecting RS.ge is not set up")
    result, taxpayer = check_company(factory(payload.service_user, payload.password), company)
    if result == "rejected":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "RS.ge rejected this service user")
    if result == "unreachable":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "RS.ge is not responding")
    row = company_connection(company, db) or CompanyRS(company_id=company.id)
    row.service_user, row.password_encrypted = payload.service_user, crypto.encrypt(payload.password)
    row.status, row.registered_name, row.vat_payer = "ok", taxpayer.name, taxpayer.vat_payer
    row.checked_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    return connection_view(row)


@company_router.post("/check", response_model=RSConnection)
def recheck(company: Company = Depends(get_company), db: Session = Depends(get_db),
            factory: RSFactory = Depends(get_rs_factory)):
    row = company_connection(company, db)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "RS.ge is not connected for this company")
    try:
        password = crypto.decrypt(row.password_encrypted)
    except crypto.CredentialsUnavailable:
        raise HTTPException(status.HTTP_409_CONFLICT, "Stored RS.ge details can't be read; connect again")
    result, taxpayer = check_company(factory(row.service_user, password), company)
    row.status, row.checked_at = result, datetime.now(timezone.utc)
    if taxpayer is not None:
        row.registered_name, row.vat_payer = taxpayer.name, taxpayer.vat_payer
    db.commit()
    return connection_view(row)


@company_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(company: Company = Depends(get_company), db: Session = Depends(get_db)):
    row = company_connection(company, db)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "RS.ge is not connected for this company")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
