"""Outgoing messages: email over SMTP and Telegram through a bot. Both are off until configured in .env."""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import settings

log = logging.getLogger(__name__)
TIMEOUT_SECONDS = 20.0


class DeliveryError(RuntimeError):
    pass


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class SMTPEmail:
    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = settings.smtp_from or settings.smtp_user
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        try:
            if settings.smtp_port == 465:
                with smtplib.SMTP_SSL(settings.smtp_host, 465, timeout=TIMEOUT_SECONDS, context=ssl.create_default_context()) as s:
                    self._send(s, message)
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SECONDS) as s:
                    s.starttls(context=ssl.create_default_context())
                    self._send(s, message)
        except (OSError, smtplib.SMTPException) as e:
            raise DeliveryError(f"email to {to}: {e}") from e

    @staticmethod
    def _send(server: smtplib.SMTP, message: EmailMessage) -> None:
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


class Telegram:
    def __init__(self, token: str, client: httpx.Client | None = None):
        self.base = f"https://api.telegram.org/bot{token}"
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)

    def _call(self, method: str, **params) -> dict | list:
        try:
            response = self.client.post(f"{self.base}/{method}", json=params)
            data = response.json()
        except (httpx.HTTPError, ValueError) as e:
            raise DeliveryError(f"telegram {method}: {e}") from e
        if not data.get("ok"):
            raise DeliveryError(f"telegram {method}: {data.get('description', 'failed')}")
        return data["result"]

    def send(self, chat_id: str, text: str) -> None:
        self._call("sendMessage", chat_id=chat_id, text=text, disable_web_page_preview=True)

    def username(self) -> str:
        return self._call("getMe")["username"]

    def updates(self, offset: int | None) -> list[dict]:
        return self._call("getUpdates", offset=offset, timeout=0, allowed_updates=["message"])


def email_sender() -> EmailSender | None:
    return SMTPEmail() if settings.smtp_host else None


def telegram() -> Telegram | None:
    return Telegram(settings.telegram_bot_token) if settings.telegram_bot_token else None


@lru_cache
def telegram_username(token: str) -> str | None:
    try:
        return Telegram(token).username()
    except DeliveryError as e:
        log.warning("Telegram bot unavailable: %s", e)
        return None
