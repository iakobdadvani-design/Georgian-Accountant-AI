"""Accountant sign-off. A rule or deadline counts as verified only while an approval of its current content stands.

Rule files keep `last_verified_date: null`; the sign-off lives in the database (who, what credentials, when,
which exact content), so nobody but a listed reviewer can mark a rule verified, and editing a rule after the
review puts it back to unverified.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RuleReview
from app.rules.calendar import get_deadlines
from app.rules.schema import Deadline, RuleResult, TaxRule

ItemKind = Literal["rule", "deadline"]
Status = Literal["verified", "unverified", "changes_requested", "outdated"]


def content_hash(item: TaxRule | Deadline) -> str:
    data = item.model_dump(mode="json", exclude={"last_verified_date"})
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class Standing:
    status: Status
    review: RuleReview | None  # the latest review of this item, of any content

    @property
    def reviewed_by(self) -> str | None:
        if self.status != "verified" or self.review is None:
            return None
        return f"{self.review.reviewer_name}, {self.review.reviewer_credentials}"


def standing(reviews: list[RuleReview], item: TaxRule | Deadline) -> Standing:
    """`reviews` for one item, oldest first."""
    if not reviews:
        return Standing("unverified", None)
    latest = reviews[-1]
    if latest.content_hash != content_hash(item):
        return Standing("outdated" if latest.decision == "approved" else "unverified", latest)
    return Standing("verified" if latest.decision == "approved" else "changes_requested", latest)


def reviews_by_item(db: Session) -> dict[tuple[str, str, int], list[RuleReview]]:
    grouped: dict[tuple[str, str, int], list[RuleReview]] = {}
    for review in db.scalars(select(RuleReview).order_by(RuleReview.created_at, RuleReview.id)):
        grouped.setdefault((review.item_kind, review.item_id, review.version), []).append(review)
    return grouped


def apply_to_results(results: list[RuleResult], rules: list[TaxRule], db: Session) -> list[RuleResult]:
    """Mark each result verified when its rule version's current content has a standing approval."""
    if not results:
        return results
    grouped = reviews_by_item(db)
    by_key = {(r.rule_id, r.version): r for r in rules}
    updated = []
    for result in results:
        rule = by_key.get((result.rule_id, result.version))
        if rule is None or rule.is_demo:
            updated.append(result)
            continue
        s = standing(grouped.get(("rule", rule.rule_id, rule.version), []), rule)
        if s.status == "verified":
            result = result.model_copy(update={"verification": "verified", "reviewed_by": s.reviewed_by,
                                               "last_verified_date": s.review.created_at.date()})
        updated.append(result)
    return updated


def deadline_standing(db: Session) -> dict[str, Standing]:
    grouped = reviews_by_item(db)
    return {d.deadline_id: standing(grouped.get(("deadline", d.deadline_id, 1), []), d) for d in get_deadlines()}

