import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TaxEventStatus


class TaxEvent(Base):
    """An obligation (filing or payment) for a period. Calendar deadlines are stored here once marked done."""

    __tablename__ = "tax_events"
    __table_args__ = (UniqueConstraint("company_id", "rule_id", "period_start", name="uq_tax_events_company_rule_period"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    tax_type: Mapped[str] = mapped_column(String(64))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    status: Mapped[TaxEventStatus] = mapped_column(
        Enum(TaxEventStatus, native_enum=False), default=TaxEventStatus.pending
    )
    rule_id: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="tax_events")
