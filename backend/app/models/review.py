import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RuleReview(Base):
    """A qualified reviewer's decision on one rule or deadline, as its content stood (content_hash).

    Editing the rule file changes the hash, so an old approval no longer counts. Rows are never updated:
    each decision is a new row, and the latest one for the current content wins.
    """

    __tablename__ = "rule_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_kind: Mapped[str] = mapped_column(String(16))  # "rule" | "deadline"
    item_id: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(default=1)
    content_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(24))  # "approved" | "changes_requested"
    notes: Mapped[str | None] = mapped_column(String(4000))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewer_name: Mapped[str] = mapped_column(String(255))
    reviewer_credentials: Mapped[str] = mapped_column(String(255))
    # Set here, to the microsecond: the latest decision wins, and two can come within the same second.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC),
                                                 server_default=func.now())
