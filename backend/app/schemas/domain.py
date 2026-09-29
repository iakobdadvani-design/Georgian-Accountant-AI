import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TaxEventStatus, TaxRegime, TransactionDirection


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CompanyCreate(BaseModel):
    name: str = Field(max_length=255)
    tax_id: str = Field(max_length=64)
    legal_form: str = Field(max_length=64)
    registration_date: date


class CompanyRead(ORMModel, CompanyCreate):
    id: uuid.UUID


class CompanyRename(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class TaxProfileUpdate(BaseModel):
    tax_regime: TaxRegime = TaxRegime.standard
    vat_registered: bool = False
    vat_registration_date: date | None = None
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)
    has_employees: bool = False
    owns_property: bool = False


class TaxProfileRead(ORMModel, TaxProfileUpdate):
    company_id: uuid.UUID


class TransactionCreate(BaseModel):
    occurred_on: date
    direction: TransactionDirection
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2, description="Total paid or received, VAT included")
    vat_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    vat_included: bool = Field(default=False, description="Work out vat_amount as the 18% VAT inside amount (rule ge.vat.output_vat)")
    currency: str = Field(default="GEL", pattern=r"^[A-Za-z]{3}$", description="ISO code; foreign currencies are translated at the NBG rate")

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, value: str) -> str:
        return value.upper()
    category: str = Field(default="other", max_length=64)
    counterparty: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    employee_id: uuid.UUID | None = None


class TransactionRead(ORMModel):
    id: uuid.UUID
    company_id: uuid.UUID
    occurred_on: date
    direction: TransactionDirection
    amount: Decimal
    vat_amount: Decimal | None
    currency: str
    exchange_rate: Decimal | None = None
    rate_date: date | None = None
    gel_amount: Decimal | None = None
    gel_vat_amount: Decimal | None = None
    category: str
    counterparty: str | None
    description: str | None
    employee_id: uuid.UUID | None
    external_id: str | None


class TaxEventCreate(BaseModel):
    tax_type: str = Field(max_length=64)
    period_start: date
    period_end: date
    due_date: date
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    status: TaxEventStatus = TaxEventStatus.pending
    rule_id: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=1000)


class TaxEventRead(ORMModel, TaxEventCreate):
    id: uuid.UUID
    company_id: uuid.UUID
