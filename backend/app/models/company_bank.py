import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CompanyBank(Base):
    """A bank account a company uses: which bank, optionally the IBAN, and whether taxes are paid from it.
    No credentials and no access to the bank."""

    __tablename__ = "company_banks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    bank_id: Mapped[str] = mapped_column(String(32))  # app.payments.BANKS
    iban: Mapped[str | None] = mapped_column(String(34))
    currency: Mapped[str] = mapped_column(String(3), default="GEL", server_default="GEL")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())  # taxes are paid from it
    last_import_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_import_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
