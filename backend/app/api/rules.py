from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.companies import get_company
from app.database import get_db
from app.models import Company, Employee
from app.rules.engine import Facts, evaluate
from app.rules.loader import get_rules
from app.rules.schema import FactValue, RuleResult, TaxRule

router = APIRouter(tags=["rules"])


class EvaluateRequest(BaseModel):
    as_of: date = Field(default_factory=date.today)
    facts: dict[str, FactValue] = {}


class CompanyEvaluateRequest(BaseModel):
    as_of: date = Field(default_factory=date.today)
    inputs: dict[str, FactValue] = Field(default={}, description="Exposed to rules as input.<name>")


def company_facts(company: Company, db: Session) -> Facts:
    facts: Facts = {
        "company.legal_form": company.legal_form,
        "company.employee_count": db.scalar(select(func.count()).where(Employee.company_id == company.id)),
    }
    if company.tax_profile is not None:
        facts["company.vat_registered"] = company.tax_profile.vat_registered
        facts["company.tax_regime"] = company.tax_profile.tax_regime.value
    return facts


@router.get("/rules", response_model=list[TaxRule])
def list_rules():
    return get_rules()


@router.post("/rules/evaluate", response_model=list[RuleResult])
def evaluate_facts(payload: EvaluateRequest):
    return evaluate(get_rules(), payload.facts, payload.as_of)


@router.post("/companies/{company_id}/evaluate", response_model=list[RuleResult])
def evaluate_company(
    payload: CompanyEvaluateRequest, company: Company = Depends(get_company), db: Session = Depends(get_db)
):
    facts = company_facts(company, db) | {f"input.{name}": value for name, value in payload.inputs.items()}
    return evaluate(get_rules(), facts, payload.as_of)
