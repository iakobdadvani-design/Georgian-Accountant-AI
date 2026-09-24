from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import get_current_user
from app.config import settings
from app.rsge import TIN_PATTERN, RSAuthError, RSClient, RSError

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
