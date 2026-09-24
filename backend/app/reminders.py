"""Deadline reminders: shortly before each open deadline, one message per user, company and channel.

Dates come from the tax calendar (api/deadlines.deadline_items); this module only decides who gets told and
remembers what was sent (reminder_log), so a restart or a second run never sends the same reminder twice.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deadlines import DeadlineItem, deadline_items
from app.i18n import format_date, t, tplural
from app.models import Company, ReminderLog, User
from app.notify import DeliveryError, EmailSender, Telegram
from app.rules.schema import localize

log = logging.getLogger(__name__)
START = re.compile(r"^/start\s+([A-Za-z0-9_-]{8,32})\s*$")


@dataclass
class Due:
    user: User
    company: Company
    items: list[DeadlineItem]


def due_for(user: User, company: Company, db: Session, today: date) -> list[DeadlineItem]:
    return [i for i in deadline_items(company, db, today, months=1)
            if i.state != "done" and 0 <= i.days_left <= user.reminder_days]


def message(due: Due, lang: str) -> tuple[str, str]:
    lines = [t("reminder.intro", lang, company=due.company.name)]
    for item in due.items:
        when = t("deadline.today", lang) if item.days_left == 0 else (
            t("deadline.tomorrow", lang) if item.days_left == 1 else tplural("deadline.in_days", item.days_left, lang))
        lines.append(t("reminder.item", lang, title=localize(item.title, lang), date=format_date(item.due_date, lang),
                       when=when))
    lines += ["", t("reminder.footer", lang)]
    subject = t("reminder.subject", lang, company=due.company.name, date=format_date(due.items[0].due_date, lang))
    return subject, "\n".join(lines)


def send_due(db: Session, today: date, email: EmailSender | None, telegram: Telegram | None) -> int:
    """Send every reminder that is due and not yet sent. Returns how many messages went out."""
    sent = 0
    users = db.scalars(select(User)).all()
    for user in users:
        channels = [c for c, ok in (("email", email and user.reminder_email),
                                    ("telegram", telegram and user.telegram_chat_id)) if ok]
        if not channels:
            continue
        lang = user.language or "ka"
        for company in user.companies:
            items = due_for(user, company, db, today)
            for channel in channels:
                done = set(db.scalars(select(ReminderLog.deadline_key).where(
                    ReminderLog.user_id == user.id, ReminderLog.company_id == company.id, ReminderLog.channel == channel)))
                fresh = [i for i in items if i.key not in done]
                if not fresh:
                    continue
                subject, body = message(Due(user, company, fresh), lang)
                try:
                    if channel == "email":
                        email.send(user.email, subject, body)
                    else:
                        telegram.send(user.telegram_chat_id, f"{subject}\n\n{body}")
                except DeliveryError as e:
                    log.warning("Reminder not sent: %s", e)
                    continue
                for item in fresh:
                    db.add(ReminderLog(user_id=user.id, company_id=company.id, deadline_key=item.key, channel=channel))
                try:
                    db.commit()
                except IntegrityError:  # another worker logged it first
                    db.rollback()
                sent += 1
    return sent


def link_telegram(db: Session, telegram: Telegram, offset: int | None) -> int | None:
    """Handle "/start <code>" messages sent to the bot; returns the next update offset."""
    try:
        updates = telegram.updates(offset)
    except DeliveryError as e:
        log.warning("Telegram polling failed: %s", e)
        return offset
    for update in updates:
        offset = update["update_id"] + 1
        msg = update.get("message") or {}
        match = START.match(msg.get("text", ""))
        chat = str((msg.get("chat") or {}).get("id", ""))
        if not chat:
            continue
        user = db.scalar(select(User).where(User.telegram_link_code == match.group(1))) if match else None
        lang = (user.language if user else None) or "ka"
        if user:
            user.telegram_chat_id, user.telegram_link_code = chat, None
            db.commit()
        try:
            telegram.send(chat, t("telegram.linked" if user else "telegram.unknown", lang))
        except DeliveryError as e:
            log.warning("Telegram reply failed: %s", e)
    return offset


async def run_forever(session_factory, email_factory, telegram_factory, interval_seconds: int) -> None:
    """Background loop started by the app: link Telegram chats every minute, send reminders every interval."""
    offset, elapsed = None, interval_seconds  # send once at startup
    while True:
        telegram = telegram_factory()

        def work(send: bool):
            with session_factory() as db:
                new_offset = link_telegram(db, telegram, offset) if telegram else offset
                count = send_due(db, date.today(), email_factory(), telegram) if send else 0
                return new_offset, count

        try:
            offset, count = await asyncio.to_thread(work, elapsed >= interval_seconds)
            if count:
                log.info("Sent %d reminder(s)", count)
        except Exception:  # never let the loop die; the next round retries
            log.exception("Reminder round failed")
        if elapsed >= interval_seconds:
            elapsed = 0
        await asyncio.sleep(60)
        elapsed += 60
