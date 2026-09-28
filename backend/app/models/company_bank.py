import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CompanyBank(Base):
    """The bank a company pays its taxes from: which bank and, optionally, the account. No credentials, no access."""

    __tablename__ = "company_banks"
    __table_args__ = (UniqueConstraint("company_id", name="uq_company_banks_company"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    bank_id: Mapped[str] = mapped_column(String(32))  # app.payments.BANKS
    iban: Mapped[str | None] = mapped_column(String(34))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
