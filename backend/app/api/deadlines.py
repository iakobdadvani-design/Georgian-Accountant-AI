from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.companies import get_company
from app.facts import company_facts
from app.database import get_db
from app.models import Company, TaxEvent
from app.models.enums import TaxEventStatus
from app.rules.calendar import get_deadlines, upcoming
from app.rules.schema import LegalSource, LocalizedText, Verification

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
    legal_source: LegalSource
    verification: Verification


class DoneUpdate(BaseModel):
    done: bool


def deadline_items(
    company: Company, db: Session, today: date, months: int = 3, include_past_done: bool = False
) -> list[DeadlineItem]:
    occurrences = upcoming(company_facts(company, db), today, months)
    done = {
        (e.rule_id, e.period_start)
        for e in db.scalars(select(TaxEvent).where(TaxEvent.company_id == company.id,
                                                   TaxEvent.status != TaxEventStatus.pending))
    }
    items = []
    for o in occurrences:
        days_left = (o.due_date - today).days
        is_done = (o.deadline.deadline_id, o.period_start) in done
        if is_done:
            state = "done"
        elif days_left < 0:
            state = "overdue"
        elif days_left <= DUE_SOON_DAYS:
            state = "due_soon"
        else:
            state = "upcoming"
        items.append(DeadlineItem(key=o.key, deadline_id=o.deadline.deadline_id, tax_type=o.deadline.tax_type,
                                  title=o.deadline.title, description=o.deadline.description,
                                  period_start=o.period_start, period_end=o.period_end, due_date=o.due_date,
                                  shifted_from=o.statutory_date if o.shifted else None, days_left=days_left, state=state, legal_source=o.deadline.legal_source,
                                  verification=o.deadline.verification))
    # Past deadlines only matter while they're still open.
    return [i for i in items if include_past_done or i.days_left >= 0 or i.state == "overdue"]


@router.get("", response_model=list[DeadlineItem])
def list_deadlines(
    months: int = Query(default=3, ge=1, le=12),
    as_of: date = Query(default_factory=date.today),
    company: Company = Depends(get_company),
    db: Session = Depends(get_db),
):
    return deadline_items(company, db, as_of, months)


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
    event.status = TaxEventStatus.filed if payload.done else TaxEventStatus.pending
    db.commit()
    return next(i for i in deadline_items(company, db, as_of, 12, include_past_done=True) if i.key == occurrence.key)
