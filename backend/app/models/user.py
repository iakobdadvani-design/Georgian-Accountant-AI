import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("telegram_link_code", name="uq_users_telegram_link_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Interface/reply language chosen by the user (app.i18n.LANGUAGES); None until they pick one.
    language: Mapped[str | None] = mapped_column(String(5))
    # Deadline reminders (app/reminders.py).
    reminder_email: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    reminder_days: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32))
    telegram_link_code: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    companies: Mapped[list["Company"]] = relationship(back_populates="owner", cascade="all, delete-orphan")

    @property
    def is_reviewer(self) -> bool:
        """Qualified accountants who may sign off rules, listed in REVIEWER_EMAILS."""
        return self.email.lower() in settings.reviewers
    sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AuthSession(Base):
    """A login. Only a SHA-256 of the cookie token is stored, so a leaked table can't be replayed."""

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="sessions")
