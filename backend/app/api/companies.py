import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Company, CompanyTaxProfile, Employee, TaxEvent, Transaction, User
from app.schemas.domain import (
    CompanyCreate,
    CompanyRead,
    EmployeeCreate,
    EmployeeRead,
    TaxEventCreate,
    TaxEventRead,
    TaxProfileRead,
    TaxProfileUpdate,
    TransactionCreate,
    TransactionRead,
)

router = APIRouter(prefix="/companies", tags=["companies"], dependencies=[Depends(get_current_user)])


def get_company(
    company_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Company:
    company = db.get(Company, company_id)
    # Someone else's company is reported exactly like a missing one, so IDs can't be probed.
    if company is None or company.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    return company


def save(db: Session, obj):
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.scalar(select(Company).where(Company.owner_id == user.id, Company.tax_id == payload.tax_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a company with this tax_id")
    return save(db, Company(owner_id=user.id, **payload.model_dump()))


@router.get("", response_model=list[CompanyRead])
def list_companies(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Company).where(Company.owner_id == user.id).order_by(Company.name)).all()


@router.get("/{company_id}", response_model=CompanyRead)
def read_company(company: Company = Depends(get_company)):
    return company


@router.get("/{company_id}/tax-profile", response_model=TaxProfileRead)
def read_tax_profile(company: Company = Depends(get_company)):
    if company.tax_profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tax profile not set")
    return company.tax_profile


@router.put("/{company_id}/tax-profile", response_model=TaxProfileRead)
def upsert_tax_profile(
    payload: TaxProfileUpdate, company: Company = Depends(get_company), db: Session = Depends(get_db)
):
    profile = company.tax_profile or CompanyTaxProfile(company_id=company.id)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    return save(db, profile)


@router.post("/{company_id}/employees", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeCreate, company: Company = Depends(get_company), db: Session = Depends(get_db)):
    duplicate = db.scalar(
        select(Employee).where(Employee.company_id == company.id, Employee.personal_id == payload.personal_id)
    )
    if duplicate:
        raise HTTPException(status.HTTP_409_CONFLICT, "An employee with this personal_id already exists")
    return save(db, Employee(company_id=company.id, **payload.model_dump()))


@router.get("/{company_id}/employees", response_model=list[EmployeeRead])
def list_employees(company: Company = Depends(get_company), db: Session = Depends(get_db)):
    return db.scalars(select(Employee).where(Employee.company_id == company.id).order_by(Employee.full_name)).all()


@router.post("/{company_id}/transactions", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate, company: Company = Depends(get_company), db: Session = Depends(get_db)
):
    if payload.employee_id is not None:
        employee = db.get(Employee, payload.employee_id)
        if employee is None or employee.company_id != company.id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "employee_id does not belong to this company")
    return save(db, Transaction(company_id=company.id, **payload.model_dump()))


@router.get("/{company_id}/transactions", response_model=list[TransactionRead])
def list_transactions(company: Company = Depends(get_company), db: Session = Depends(get_db)):
    return db.scalars(
        select(Transaction).where(Transaction.company_id == company.id).order_by(Transaction.occurred_on)
    ).all()


@router.post("/{company_id}/tax-events", response_model=TaxEventRead, status_code=status.HTTP_201_CREATED)
def create_tax_event(payload: TaxEventCreate, company: Company = Depends(get_company), db: Session = Depends(get_db)):
    if payload.period_end < payload.period_start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "period_end is before period_start")
    return save(db, TaxEvent(company_id=company.id, **payload.model_dump()))


@router.get("/{company_id}/tax-events", response_model=list[TaxEventRead])
def list_tax_events(company: Company = Depends(get_company), db: Session = Depends(get_db)):
    return db.scalars(select(TaxEvent).where(TaxEvent.company_id == company.id).order_by(TaxEvent.due_date)).all()
