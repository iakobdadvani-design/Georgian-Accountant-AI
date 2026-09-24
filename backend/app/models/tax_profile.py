import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TaxRegime


class CompanyTaxProfile(Base):
    """Facts about a company that tax rules will condition on. Holds no rules itself."""

    __tablename__ = "company_tax_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), unique=True)
    tax_regime: Mapped[TaxRegime] = mapped_column(Enum(TaxRegime, native_enum=False), default=TaxRegime.standard)
    vat_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    vat_registration_date: Mapped[date | None] = mapped_column(Date)
    fiscal_year_start_month: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="tax_profile")
