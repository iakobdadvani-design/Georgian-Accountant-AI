import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Company(Base):
    __tablename__ = "companies"
    # Unique per owner, not globally: an owner and their accountant may both add the same company.
    __table_args__ = (UniqueConstraint("owner_id", "tax_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    tax_id: Mapped[str] = mapped_column(String(64))
    legal_form: Mapped[str] = mapped_column(String(64))
    registration_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="companies")
    tax_profile: Mapped["CompanyTaxProfile | None"] = relationship(
        back_populates="company", cascade="all, delete-orphan", uselist=False
    )
    employees: Mapped[list["Employee"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    tax_events: Mapped[list["TaxEvent"]] = relationship(back_populates="company", cascade="all, delete-orphan")
