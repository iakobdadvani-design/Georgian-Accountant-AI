import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

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


class TaxProfileUpdate(BaseModel):
    tax_regime: TaxRegime = TaxRegime.standard
    vat_registered: bool = False
    vat_registration_date: date | None = None
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)


class TaxProfileRead(ORMModel, TaxProfileUpdate):
    company_id: uuid.UUID


class EmployeeCreate(BaseModel):
    full_name: str = Field(max_length=255)
    personal_id: str = Field(max_length=32)
    gross_monthly_salary: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="GEL", min_length=3, max_length=3)
    pension_participant: bool = True
    hired_on: date
    terminated_on: date | None = None


class EmployeeRead(ORMModel, EmployeeCreate):
    id: uuid.UUID
    company_id: uuid.UUID


class TransactionCreate(BaseModel):
    occurred_on: date
    direction: TransactionDirection
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="GEL", min_length=3, max_length=3)
    category: str = Field(max_length=64)
    counterparty: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    employee_id: uuid.UUID | None = None


class TransactionRead(ORMModel, TransactionCreate):
    id: uuid.UUID
    company_id: uuid.UUID


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
