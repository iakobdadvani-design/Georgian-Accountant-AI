"""Accountant sign-off of rules and deadlines. Anyone signed in can see the status; only reviewers can decide."""

import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import RuleReview, User
from app.reviews import ItemKind, Status, content_hash, reviews_by_item, standing
from app.rules.calendar import get_deadlines
from app.rules.loader import get_rules
from app.rules.schema import Deadline, LegalSource, LocalizedText, TaxRule

router = APIRouter(prefix="/reviews", tags=["reviews"], dependencies=[Depends(get_current_user)])


class ReviewRead(BaseModel):
    id: uuid.UUID
    decision: Literal["approved", "changes_requested"]
    notes: str | None
    reviewer_name: str
    reviewer_credentials: str
    content_hash: str
    created_at: datetime


class ReviewItem(BaseModel):
    kind: ItemKind
    item_id: str
    version: int
    title: LocalizedText
    tax_type: str
    effective_from: date | None
    effective_to: date | None
    legal_source: LegalSource
    status: Status
    content_hash: str
    content: dict = Field(description="The rule or deadline exactly as reviewed")
    history: list[ReviewRead]


class ReviewList(BaseModel):
    can_review: bool
    items: list[ReviewItem]


class ReviewCreate(BaseModel):
    decision: Literal["approved", "changes_requested"]
    credentials: str = Field(min_length=3, max_length=255, description="Qualification, e.g. certified accountant + number")
    notes: str | None = Field(default=None, max_length=4000)
    content_hash: str = Field(min_length=64, max_length=64, description="Hash of the content the reviewer looked at")


def items() -> list[tuple[ItemKind, str, int, TaxRule | Deadline]]:
    rules: list = [("rule", r.rule_id, r.version, r) for r in get_rules() if not r.is_demo]
    return rules + [("deadline", d.deadline_id, 1, d) for d in get_deadlines()]


def to_item(kind: ItemKind, item_id: str, version: int, obj: TaxRule | Deadline, history: list[RuleReview]) -> ReviewItem:
    return ReviewItem(
        kind=kind, item_id=item_id, version=version, title=obj.title, tax_type=obj.tax_type,
        effective_from=getattr(obj, "effective_from", None), effective_to=getattr(obj, "effective_to", None),
        legal_source=obj.legal_source, status=standing(history, obj).status, content_hash=content_hash(obj),
        content=obj.model_dump(mode="json", exclude={"last_verified_date"}),
        history=[ReviewRead.model_validate(r, from_attributes=True) for r in reversed(history)])


@router.get("", response_model=ReviewList)
def list_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    grouped = reviews_by_item(db)
    return ReviewList(can_review=user.is_reviewer, items=[
        to_item(kind, item_id, version, obj, grouped.get((kind, item_id, version), []))
        for kind, item_id, version, obj in items()])


@router.post("/{kind}/{item_id}/{version}", response_model=ReviewItem, status_code=status.HTTP_201_CREATED)
def review(
    kind: ItemKind, item_id: str, version: int, payload: ReviewCreate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    if not user.is_reviewer:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only reviewers can sign off rules")
    found = next((obj for k, i, v, obj in items() if (k, i, v) == (kind, item_id, version)), None)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown rule or deadline")
    # The reviewer must have seen the current content; a file changed since the page loaded is refused.
    if payload.content_hash != content_hash(found):
        raise HTTPException(status.HTTP_409_CONFLICT, "The rule changed since you opened it; reload and review again")
    db.add(RuleReview(item_kind=kind, item_id=item_id, version=version, content_hash=payload.content_hash,
                      decision=payload.decision, notes=(payload.notes or "").strip() or None, reviewer_id=user.id,
                      reviewer_name=user.full_name, reviewer_credentials=payload.credentials.strip()))
    db.commit()
    history = reviews_by_item(db).get((kind, item_id, version), [])
    return to_item(kind, item_id, version, found, history)
