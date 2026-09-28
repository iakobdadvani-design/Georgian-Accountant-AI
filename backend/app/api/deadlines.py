from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.books import run, summary
from app.api.companies import get_company
from app.facts import company_facts
from app.database import get_db
from app.models import Company, TaxEvent
from app.models.enums import TaxEventStatus
from app.payments import AMOUNT_FROM_BOOKS
from app.reviews import deadline_standing
from app.rules.calendar import get_deadlines, upcoming
from app.rules.lateness import lateness
from app.rules.schema import LegalSource, LocalizedText, RuleResult, Verification

router = APIRouter(prefix="/companies/{company_id}/deadlines", tags=["deadlines"])

DUE_SOON_DAYS = 7


class DeadlineItem(BaseModel):
    key: str
    deadline_id: str
    tax_type: str
    title: LocalizedText
    description: LocalizedText | None
    period_start: date
    period_end: date
    due_date: date
    shifted_from: date | None = None  # the statutory date, when it fell on a day off
    days_left: int
    state: Literal["done", "overdue", "due_soon", "upcoming"]
    payment: bool  # False: a return with nothing to pay
    amount_due: Decimal | None = None  # from the rule run on the period's recorded sales, when there are any
    paid_amount: Decimal | None = None
    penalties: list[RuleResult] = []  # overdue with a known amount: interest and fine if paid and filed on as_of
    legal_source: LegalSource
    verification: Verification
    reviewed_by: str | None = None


class DoneUpdate(BaseModel):
    done: bool
    paid_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2,
                                        description="With done: record the deadline as paid, with this amount")
    paid_on: date | None = Field(default=None, description="When it was paid; default: as_of")


def amount_due(company: Company, db: Session, deadline_id: str, period_start: date) -> Decimal | None:
    """The amount the rules give for this period from the recorded sales and purchases; None without records."""
    field = AMOUNT_FROM_BOOKS.get(deadline_id)
    if field is None:
        return None
    figures = summary(company, db, period_start)
    result = getattr(figures, field)
    if not figures.totals.count or result is None or result.status != "applies":
        return None
    return result.amount


def penalties(company: Company, db: Session, due: date, tax: Decimal, today: date) -> list[RuleResult]:
    """Late payment interest and the late filing fine on `tax` if it's paid and filed `today` (rules, with sign-offs)."""
    late = lateness(due, today)
    facts = {**company_facts(company, db), "input.tax_due": str(tax), "input.days_late": late.days,
             "input.months_late": late.months}
    results = [run(rule_id, facts, today, db) for rule_id in ("ge.penalty.late_payment", "ge.penalty.late_filing")]
    return [r for r in results if r is not None and r.status == "applies"]


def deadline_items(
    company: Company, db: Session, today: date, months: int = 3, include_past_done: bool = False,
    with_amounts: bool = False,
) -> list[DeadlineItem]:
    occurrences = upcoming(company_facts(company, db), today, months)
    done = {
        (e.rule_id, e.period_start): e
        for e in db.scalars(select(TaxEvent).where(TaxEvent.company_id == company.id,
                                                   TaxEvent.status != TaxEventStatus.pending))
    }
    signed = deadline_standing(db)
    items = []
    for o in occurrences:
        days_left = (o.due_date - today).days
        event = done.get((o.deadline.deadline_id, o.period_start))
        is_done = event is not None
        if is_done:
            state = "done"
        elif days_left < 0:
            state = "overdue"
        elif days_left <= DUE_SOON_DAYS:
            state = "due_soon"
        else:
            state = "upcoming"
        due_amount = (amount_due(company, db, o.deadline.deadline_id, o.period_start)
                      if with_amounts and not is_done and o.deadline.payment else None)
        items.append(DeadlineItem(key=o.key, deadline_id=o.deadline.deadline_id, tax_type=o.deadline.tax_type,
                                  title=o.deadline.title, description=o.deadline.description,
                                  period_start=o.period_start, period_end=o.period_end, due_date=o.due_date,
                                  shifted_from=o.statutory_date if o.shifted else None, days_left=days_left, state=state,
                                  payment=o.deadline.payment,
                                  amount_due=due_amount,
                                  penalties=penalties(company, db, o.due_date, due_amount, today)
                                  if state == "overdue" and due_amount else [],
                                  paid_amount=event.amount if event is not None and event.status == TaxEventStatus.paid else None,
                                  legal_source=o.deadline.legal_source,
                                  verification="verified" if signed[o.deadline.deadline_id].status == "verified"
                                  else o.deadline.verification,
                                  reviewed_by=signed[o.deadline.deadline_id].reviewed_by))
    # Past deadlines only matter while they're still open.
    return [i for i in items if include_past_done or i.days_left >= 0 or i.state == "overdue"]


@router.get("", response_model=list[DeadlineItem])
def list_deadlines(
    months: int = Query(default=3, ge=1, le=12),
    as_of: date = Query(default_factory=date.today),
    company: Company = Depends(get_company),
    db: Session = Depends(get_db),
):
    return deadline_items(company, db, as_of, months, with_amounts=True)


@router.put("/{deadline_id}/{period_start}", response_model=DeadlineItem)
def mark_done(
    deadline_id: str,
    period_start: date,
    payload: DoneUpdate,
    as_of: date = Query(default_factory=date.today),
    company: Company = Depends(get_company),
    db: Session = Depends(get_db),
):
    deadline = next((d for d in get_deadlines() if d.deadline_id == deadline_id), None)
    if deadline is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown deadline")
    occurrence = next((o for o in upcoming(company_facts(company, db), as_of, 12, [deadline])
                       if o.period_start == period_start), None)
    if occurrence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such deadline for this company and period")

    event = db.scalar(select(TaxEvent).where(TaxEvent.company_id == company.id, TaxEvent.rule_id == deadline_id,
                                             TaxEvent.period_start == period_start))
    if event is None:
        event = TaxEvent(company_id=company.id, rule_id=deadline_id, tax_type=deadline.tax_type,
                         period_start=occurrence.period_start, period_end=occurrence.period_end,
                         due_date=occurrence.due_date)
        db.add(event)
    if payload.paid_amount is not None and not (payload.done and deadline.payment):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A paid amount needs done=true on a deadline with a payment")
    paid = payload.done and payload.paid_amount is not None
    event.status = TaxEventStatus.paid if paid else TaxEventStatus.filed if payload.done else TaxEventStatus.pending
    event.amount = payload.paid_amount if paid else None
    event.paid_on = (payload.paid_on or as_of) if paid else None
    db.commit()
    return next(i for i in deadline_items(company, db, as_of, 12, include_past_done=True, with_amounts=True)
                if i.key == occurrence.key)
