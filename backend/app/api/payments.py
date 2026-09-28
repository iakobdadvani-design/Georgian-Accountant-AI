from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.companies import get_company
from app.database import get_db
from app.models import Company, CompanyBank, TaxEvent
from app.models.enums import TaxEventStatus
from app.payments import BANKS, PaymentDetails, normalize_iban
from app.rules.calendar import get_deadlines
from app.rules.schema import LocalizedText

router = APIRouter(tags=["payments"])


@router.get("/payments", response_model=PaymentDetails)
def payment_details():
    """What to enter in a bank's treasury payment order; the same for every tax."""
    return PaymentDetails()


class BankChoice(BaseModel):
    bank_id: str
    iban: str | None = Field(default=None, max_length=40)

    @field_validator("bank_id")
    @classmethod
    def known_bank(cls, value: str) -> str:
        if value not in {b.id for b in BANKS}:
            raise ValueError("unknown bank")
        return value

    @field_validator("iban")
    @classmethod
    def valid_iban(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        iban = normalize_iban(value)
        if iban is None:
            raise ValueError("not a valid Georgian IBAN")
        return iban


def saved_bank(company: Company, db: Session) -> CompanyBank | None:
    return db.scalar(select(CompanyBank).where(CompanyBank.company_id == company.id))


@router.get("/companies/{company_id}/bank", response_model=BankChoice | None)
def get_bank(company: Company = Depends(get_company), db: Session = Depends(get_db)):
    """The bank this company pays from, or null. Stored for convenience only: the app has no access to it."""
    bank = saved_bank(company, db)
    return BankChoice(bank_id=bank.bank_id, iban=bank.iban) if bank else None


@router.put("/companies/{company_id}/bank", response_model=BankChoice)
def set_bank(payload: BankChoice, company: Company = Depends(get_company), db: Session = Depends(get_db)):
    bank = saved_bank(company, db) or CompanyBank(company_id=company.id)
    bank.bank_id, bank.iban = payload.bank_id, payload.iban
    db.add(bank)
    db.commit()
    return payload


@router.delete("/companies/{company_id}/bank", status_code=status.HTTP_204_NO_CONTENT)
def remove_bank(company: Company = Depends(get_company), db: Session = Depends(get_db)):
    bank = saved_bank(company, db)
    if bank is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bank saved")
    db.delete(bank)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class PaidItem(BaseModel):
    deadline_id: str
    title: LocalizedText
    period_start: date
    period_end: date
    due_date: date
    amount: Decimal
    paid_on: date | None


@router.get("/companies/{company_id}/payments/history", response_model=list[PaidItem])
def payment_history(company: Company = Depends(get_company), db: Session = Depends(get_db)):
    """Taxes marked paid in the app, newest first."""
    titles = {d.deadline_id: d.title for d in get_deadlines()}
    events = db.scalars(select(TaxEvent).where(TaxEvent.company_id == company.id,
                                               TaxEvent.status == TaxEventStatus.paid))
    items = [PaidItem(deadline_id=e.rule_id, title=titles[e.rule_id], period_start=e.period_start,
                      period_end=e.period_end, due_date=e.due_date, amount=e.amount, paid_on=e.paid_on)
             for e in events if e.rule_id in titles and e.amount is not None]
    return sorted(items, key=lambda i: (i.paid_on or i.due_date, i.period_start), reverse=True)
