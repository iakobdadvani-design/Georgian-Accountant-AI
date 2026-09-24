"""Deadline reminders by email and Telegram, with fake senders (no network)."""

from datetime import date

import pytest
from sqlalchemy import select

from app.api.reminders import get_email, get_telegram
from app.database import get_db
from app.main import app
from app.models import User
from app.notify import DeliveryError
from app.reminders import link_telegram, send_due

TODAY = date(2026, 10, 13)  # VAT for September is due 15 October: 2 days away


class FakeEmail:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def send(self, to, subject, body):
        if self.fail:
            raise DeliveryError("smtp down")
        self.sent.append((to, subject, body))


class FakeTelegram:
    def __init__(self, updates=()):
        self.sent, self._updates = [], list(updates)

    def send(self, chat_id, text):
        self.sent.append((chat_id, text))

    def updates(self, offset):
        return [u for u in self._updates if offset is None or u["update_id"] >= offset]

    def username(self):
        return "georgian_tax_bot"


@pytest.fixture
def db(client):
    session = next(app.dependency_overrides[get_db]())
    yield session
    session.close()


@pytest.fixture
def vat_company(client):
    company = client.post("/companies", json={"name": "Remind LLC", "tax_id": "404000999", "legal_form": "LLC",
                                              "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": True})
    return company


def owner(db) -> User:
    return db.scalar(select(User).where(User.email == "owner@example.com"))


def test_nothing_is_sent_until_a_channel_is_on(client, vat_company, db):
    email = FakeEmail()
    assert send_due(db, TODAY, email, FakeTelegram()) == 0
    assert email.sent == []


def test_email_reminder_once_per_deadline(client, vat_company, db):
    client.put("/reminders", json={"email_enabled": True, "days_before": 3})
    email = FakeEmail()
    assert send_due(db, TODAY, email, None) == 1
    [(to, subject, body)] = email.sent
    assert to == "owner@example.com"
    assert "Remind LLC" in subject and "15 ოქტომბერი 2026" in subject  # the account's language, Georgian by default
    assert "დღგ-ის დეკლარაცია და გადახდა" in body and "2 დღეში" in body
    assert "მოგების გადასახადის დეკლარაცია" in body  # LLCs also file the monthly profit tax return
    assert send_due(db, TODAY, email, None) == 0  # already sent
    assert send_due(db, date(2026, 10, 14), email, None) == 0


def test_outside_the_window_or_done_is_not_sent(client, vat_company, db):
    client.put("/reminders", json={"email_enabled": True, "days_before": 1})
    email = FakeEmail()
    assert send_due(db, TODAY, email, None) == 0  # 2 days away, window is 1
    for deadline in ("ge.vat.monthly_return", "ge.profit.monthly_return"):
        client.put(f"/companies/{vat_company['id']}/deadlines/{deadline}/2026-09-01", params={"as_of": "2026-10-14"},
                   json={"done": True})
    assert send_due(db, date(2026, 10, 14), email, None) == 0


def test_failed_delivery_is_retried_later(client, vat_company, db):
    client.put("/reminders", json={"email_enabled": True, "days_before": 3})
    assert send_due(db, TODAY, FakeEmail(fail=True), None) == 0
    email = FakeEmail()
    assert send_due(db, TODAY, email, None) == 1


def test_telegram_link_then_reminder(client, vat_company, db):
    app.dependency_overrides[get_telegram] = lambda: FakeTelegram()
    import app.api.reminders as api
    original = api.telegram_username
    api.telegram_username = lambda token: "georgian_tax_bot"
    try:
        url = client.post("/reminders/telegram").json()["url"]
    finally:
        api.telegram_username = original
    assert url.startswith("https://t.me/georgian_tax_bot?start=")
    code = url.rsplit("=", 1)[1]

    bot = FakeTelegram(updates=[
        {"update_id": 7, "message": {"text": "/start wrongcode123", "chat": {"id": 111}}},
        {"update_id": 8, "message": {"text": f"/start {code}", "chat": {"id": 222}}},
    ])
    assert link_telegram(db, bot, None) == 9
    assert [chat for chat, _ in bot.sent] == ["111", "222"]
    assert "ვადა გაუვიდა" in bot.sent[0][1] and "დაკავშირებულია" in bot.sent[1][1]
    db.expire_all()
    assert owner(db).telegram_chat_id == "222" and owner(db).telegram_link_code is None

    bot.sent.clear()
    assert send_due(db, TODAY, None, bot) == 1
    assert bot.sent[0][0] == "222" and "Remind LLC" in bot.sent[0][1]
    assert client.get("/reminders").json()["telegram_linked"] is True
    assert client.delete("/reminders/telegram").status_code == 204
    assert client.get("/reminders").json()["telegram_linked"] is False


def test_settings_api(client):
    app.dependency_overrides[get_email] = lambda: FakeEmail()
    app.dependency_overrides[get_telegram] = lambda: None
    assert client.get("/reminders").json() == {"email_available": True, "email_enabled": False,
                                              "telegram_available": False, "telegram_linked": False, "days_before": 3}
    body = client.put("/reminders", json={"email_enabled": True, "days_before": 7}).json()
    assert (body["email_enabled"], body["days_before"]) == (True, 7)
    assert client.put("/reminders", json={"email_enabled": True, "days_before": 30}).status_code == 422
    assert client.post("/reminders/telegram").status_code == 503


def test_send_test_message(client):
    email = FakeEmail()
    app.dependency_overrides[get_email] = lambda: email
    app.dependency_overrides[get_telegram] = lambda: None
    client.put("/reminders", json={"email_enabled": True, "days_before": 3})
    assert client.post("/reminders/test").json() == {"sent": ["email"], "failed": []}
    assert email.sent[0][1] == "სატესტო შეხსენება ქართული AI ბუღალტრისგან"
