"""A company's employees and each month's salary figures for the RS.ge withholding return.

The app keeps the list and runs the payroll rule for each employee; it doesn't file anything with RS.ge. The owner
copies the figures into the declaration on the RS.ge portal (Tax Code Art. 154(3)-(4)).
"""

import re
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.books import run
from app.api.companies import get_company
from app.books import month_end, month_start
from app.database import get_db
from app.facts import company_facts
from app.models import Company, Employee
from app.rules.calendar import get_deadlines, upcoming
from app.rules.schema import RuleResult

router = APIRouter(prefix="/companies/{company_id}", tags=["employees"])

PERSONAL_ID = re.compile(r"^[A-Za-z0-9]{5,32}$")  # Georgian citizens: 11 digits; foreigners: their document number
WITHHOLDING_RETURN = "ge.withholding.monthly_return"


class EmployeeIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    personal_id: str
    gross_monthly_salary: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    pension_participant: bool = True
    hired_on: date
    terminated_on: date | None = None

    @field_validator("full_name")
    @classmethod
    def trimmed(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name is empty")
        return value.strip()

    @field_validator("personal_id")
    @classmethod
    def valid_personal_id(cls, value: str) -> str:
        value = re.sub(r"\s+", "", value)
        if not PERSONAL_ID.match(value):
            raise ValueError("personal number: 11 digits, or a foreign document number")
        return value

    @model_validator(mode="after")
    def left_after_joining(self) -> "EmployeeIn":
        if self.terminated_on is not None and self.terminated_on < self.hired_on:
            raise ValueError("the leaving date is before the start date")
        return self


class EmployeeOut(EmployeeIn):
    id: uuid.UUID
    currency: str = "GEL"  # salaries are in lari


def as_read(e: Employee) -> EmployeeOut:
    return EmployeeOut(id=e.id, currency=e.currency, full_name=e.full_name, personal_id=e.personal_id,
                       gross_monthly_salary=e.gross_monthly_salary, pension_participant=e.pension_participant,
                       hired_on=e.hired_on, terminated_on=e.terminated_on)


def employees_of(company: Company, db: Session) -> list[Employee]:
    rows = db.scalars(select(Employee).where(Employee.company_id == company.id)).all()
    return sorted(rows, key=lambda e: (e.terminated_on is not None, e.full_name.lower(), str(e.id)))


def get_employee(employee_id: uuid.UUID, company: Company = Depends(get_company), db: Session = Depends(get_db)) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None or employee.company_id != company.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such employee")
    return employee


def taken(company: Company, db: Session, personal_id: str, other_than: uuid.UUID | None = None) -> bool:
    return any(e.personal_id == personal_id and e.id != other_than for e in employees_of(company, db))


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(company: Company = Depends(get_company), db: Session = Depends(get_db)):
    """Current employees first, then those who have left."""
    return [as_read(e) for e in employees_of(company, db)]


@router.post("/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def add_employee(payload: EmployeeIn, company: Company = Depends(get_company), db: Session = Depends(get_db)):
    if taken(company, db, payload.personal_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "An employee with this personal number is already on the list")
    employee = Employee(company_id=company.id, currency="GEL", **payload.model_dump())
    db.add(employee)
    db.commit()
    return as_read(employee)


@router.put("/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(payload: EmployeeIn, employee: Employee = Depends(get_employee),
                    company: Company = Depends(get_company), db: Session = Depends(get_db)):
    if taken(company, db, payload.personal_id, other_than=employee.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "An employee with this personal number is already on the list")
    for name, value in payload.model_dump().items():
        setattr(employee, name, value)
    db.commit()
    return as_read(employee)


@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_employee(employee: Employee = Depends(get_employee), db: Session = Depends(get_db)):
    db.delete(employee)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class PayrollLine(BaseModel):
    employee: EmployeeOut
    result: RuleResult  # ge.payroll.income_tax on this employee's monthly gross salary


class PayrollMonth(BaseModel):
    period_start: date
    period_end: date
    return_due: date | None  # the withholding return for this month (RS.ge), if the company has one
    lines: list[PayrollLine]
    totals: dict[str, Decimal]  # each breakdown line added up over the employees


def employed_during(e: Employee, start: date, end: date) -> bool:
    return e.hired_on <= end and (e.terminated_on is None or e.terminated_on >= start)


@router.get("/payroll", response_model=PayrollMonth)
def payroll(month: date = Query(default_factory=date.today, description="Any day of the month"),
            company: Company = Depends(get_company), db: Session = Depends(get_db)):
    """The payroll rule for everyone employed during the month, on their monthly gross salary."""
    start, end = month_start(month), month_end(month)
    facts = company_facts(company, db)
    lines = []
    for e in employees_of(company, db):
        if not employed_during(e, start, end):
            continue
        result = run("ge.payroll.income_tax", {**facts, "input.gross_salary": str(e.gross_monthly_salary),
                                                "input.pension_participant": e.pension_participant}, end, db)
        if result is not None:
            lines.append(PayrollLine(employee=as_read(e), result=result))
    totals: dict[str, Decimal] = {"gross_salary": sum((line.employee.gross_monthly_salary for line in lines), Decimal("0"))}
    for line in lines:
        for item in line.result.breakdown:
            totals[item.name] = totals.get(item.name, Decimal("0")) + item.amount
    deadline = [d for d in get_deadlines() if d.deadline_id == WITHHOLDING_RETURN]
    due = next((o.due_date for o in upcoming(facts, start, 3, deadline) if o.period_start == start), None)
    return PayrollMonth(period_start=start, period_end=end, return_due=due, lines=lines, totals=totals)
