from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.companies import get_company
from app.database import get_db
from app.facts import company_facts
from app.models import Company
from app.reviews import apply_to_results
from app.rules.engine import evaluate
from app.rules.loader import get_rules
from app.rules.schema import FactValue, RuleResult, TaxRule

router = APIRouter(tags=["rules"])


class EvaluateRequest(BaseModel):
    as_of: date = Field(default_factory=date.today)
    facts: dict[str, FactValue] = {}


class CompanyEvaluateRequest(BaseModel):
    as_of: date = Field(default_factory=date.today)
    inputs: dict[str, FactValue] = Field(default={}, description="Exposed to rules as input.<name>")


@router.get("/rules", response_model=list[TaxRule])
def list_rules():
    return get_rules()


@router.post("/rules/evaluate", response_model=list[RuleResult])
def evaluate_facts(payload: EvaluateRequest, db: Session = Depends(get_db)):
    return apply_to_results(evaluate(get_rules(), payload.facts, payload.as_of), get_rules(), db)


@router.post("/companies/{company_id}/evaluate", response_model=list[RuleResult])
def evaluate_company(
    payload: CompanyEvaluateRequest, company: Company = Depends(get_company), db: Session = Depends(get_db)
):
    facts = company_facts(company, db) | {f"input.{name}": value for name, value in payload.inputs.items()}
    return apply_to_results(evaluate(get_rules(), facts, payload.as_of), get_rules(), db)
