import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TransactionDirection


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    direction: Mapped[TransactionDirection] = mapped_column(Enum(TransactionDirection, native_enum=False))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="GEL")
    category: Mapped[str] = mapped_column(String(64))
    counterparty: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="transactions")
