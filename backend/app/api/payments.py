import uuid
from datetime import UTC, date, datetime
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


CURRENCIES = ("GEL", "USD", "EUR", "GBP")


class BankAccountIn(BaseModel):
    bank_id: str
    iban: str | None = Field(default=None, max_length=40)
    currency: str = "GEL"
    is_primary: bool = False

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

    @field_validator("currency")
    @classmethod
    def known_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in CURRENCIES:
            raise ValueError(f"currency must be one of {', '.join(CURRENCIES)}")
        return value


class BankAccount(BankAccountIn):
    id: uuid.UUID
    last_import_at: datetime | None = None
    last_import_count: int | None = None


def bank_accounts(company: Company, db: Session) -> list[CompanyBank]:
    """Taxes-from account first, then in the order they were added."""
    rows = db.scalars(select(CompanyBank).where(CompanyBank.company_id == company.id)).all()
    return sorted(rows, key=lambda b: (not b.is_primary, b.created_at or datetime.min.replace(tzinfo=UTC), str(b.id)))


def as_read(bank: CompanyBank) -> BankAccount:
    return BankAccount(id=bank.id, bank_id=bank.bank_id, iban=bank.iban, currency=bank.currency,
                       is_primary=bank.is_primary, last_import_at=bank.last_import_at,
                       last_import_count=bank.last_import_count)


def get_bank_account(bank_account_id: uuid.UUID, company: Company = Depends(get_company),
                     db: Session = Depends(get_db)) -> CompanyBank:
    bank = db.get(CompanyBank, bank_account_id)
    if bank is None or bank.company_id != company.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such bank account")
    return bank


def make_primary(company: Company, db: Session, bank: CompanyBank) -> None:
    for other in bank_accounts(company, db):
        other.is_primary = other.id == bank.id


@router.get("/companies/{company_id}/banks", response_model=list[BankAccount])
def list_banks(company: Company = Depends(get_company), db: Session = Depends(get_db)):
    """The company's bank accounts. Stored for convenience only: the app has no access to any bank."""
    return [as_read(b) for b in bank_accounts(company, db)]


@router.post("/companies/{company_id}/banks", response_model=BankAccount, status_code=status.HTTP_201_CREATED)
def add_bank(payload: BankAccountIn, company: Company = Depends(get_company), db: Session = Depends(get_db)):
    first = not bank_accounts(company, db)
    bank = CompanyBank(company_id=company.id, bank_id=payload.bank_id, iban=payload.iban, currency=payload.currency,
                       is_primary=False, created_at=datetime.now(UTC))
    db.add(bank)
    db.flush()
    if payload.is_primary or first:  # the first account is where taxes are paid from until changed
        make_primary(company, db, bank)
    db.commit()
    return as_read(bank)


@router.put("/companies/{company_id}/banks/{bank_account_id}", response_model=BankAccount)
def update_bank(payload: BankAccountIn, bank: CompanyBank = Depends(get_bank_account),
                company: Company = Depends(get_company), db: Session = Depends(get_db)):
    bank.bank_id, bank.iban, bank.currency = payload.bank_id, payload.iban, payload.currency
    if payload.is_primary:
        make_primary(company, db, bank)
    db.commit()
    return as_read(bank)


@router.delete("/companies/{company_id}/banks/{bank_account_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_bank(bank: CompanyBank = Depends(get_bank_account), company: Company = Depends(get_company),
                db: Session = Depends(get_db)):
    was_primary = bank.is_primary
    db.delete(bank)
    db.flush()
    rest = bank_accounts(company, db)
    if was_primary and rest:
        make_primary(company, db, rest[0])
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
