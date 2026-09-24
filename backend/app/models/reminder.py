import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReminderLog(Base):
    """One reminder sent: a deadline occurrence (DeadlineItem.key) for a company, to a user, on a channel."""

    __tablename__ = "reminder_log"
    __table_args__ = (UniqueConstraint("user_id", "company_id", "deadline_key", "channel", name="uq_reminder_log_once"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    deadline_key: Mapped[str] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(16))  # "email" | "telegram"
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
