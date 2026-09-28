import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CompanyRS(Base):
    """A company's RS.ge service user (never the portal login), its password encrypted (app.crypto), and what RS
    last said about the company. RS values are shown next to the profile; they change it only when the user applies them."""

    __tablename__ = "company_rs"
    __table_args__ = (UniqueConstraint("company_id", name="uq_company_rs_company"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    service_user: Mapped[str] = mapped_column(String(100))
    password_encrypted: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))  # "ok" | "rejected" | "unreachable"
    registered_name: Mapped[str | None] = mapped_column(String(255))
    vat_payer: Mapped[bool | None] = mapped_column(Boolean)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
