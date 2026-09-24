"""Going-public protections: sign-in limits, password reset by email, security headers, privacy page."""

import re

from conftest import PASSWORD
from app.api.reminders import get_email
from app.main import app


class Mailbox:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append((to, subject, body))

    def link(self):
        return re.search(r"#reset=([\w-]+)", self.sent[-1][2]).group(1)


def test_repeated_wrong_passwords_are_blocked_then_right_one_too(make_client):
    make_client("victim@example.com")
    attacker = make_client()
    for _ in range(5):
        assert attacker.post("/auth/login", json={"email": "victim@example.com", "password": "wrong-guess"}).status_code == 401
    blocked = attacker.post("/auth/login", json={"email": "victim@example.com", "password": PASSWORD})
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many attempts. Please wait a few minutes and try again."


def test_successful_login_clears_the_count(make_client):
    make_client("user@example.com")
    c = make_client()
    for _ in range(4):
        c.post("/auth/login", json={"email": "user@example.com", "password": "nope-nope"})
    assert c.post("/auth/login", json={"email": "user@example.com", "password": PASSWORD}).status_code == 200
    for _ in range(4):
        assert c.post("/auth/login", json={"email": "user@example.com", "password": "nope-nope"}).status_code == 401


def test_registration_is_limited_per_address(make_client):
    c = make_client()
    codes = [c.post("/auth/register", json={"email": f"bulk{i}@example.com", "password": PASSWORD, "full_name": "B"}).status_code
             for i in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429


def test_reset_needs_email_configured(make_client):
    assert make_client().get("/auth/features").json() == {"password_reset": False}
    assert make_client().post("/auth/password-reset", json={"email": "x@example.com"}).status_code == 503


def test_password_reset_flow(make_client):
    mailbox = Mailbox()
    app.dependency_overrides[get_email] = lambda: mailbox
    owner = make_client("reset@example.com")
    assert owner.get("/auth/me").status_code == 200
    anon = make_client()
    assert anon.get("/auth/features").json() == {"password_reset": True}

    # Unknown emails get the same answer and no mail.
    assert anon.post("/auth/password-reset", json={"email": "nobody@example.com"}).status_code == 202
    assert mailbox.sent == []

    assert anon.post("/auth/password-reset", json={"email": "Reset@Example.com", "language": "en"}).status_code == 202
    to, subject, body = mailbox.sent[0]
    assert to == "reset@example.com" and subject == "Reset your password"
    assert "http://localhost:8000/#reset=" in body and "expires in 1 hour" in body
    token = mailbox.link()

    assert anon.post("/auth/password-reset/confirm", json={"token": token, "password": "short"}).status_code == 422
    assert anon.post("/auth/password-reset/confirm", json={"token": token, "password": "brand new secret"}).status_code == 204
    # Used once only, and every old session is signed out.
    again = anon.post("/auth/password-reset/confirm", json={"token": token, "password": "another secret"})
    assert again.status_code == 400 and again.json()["detail"] == "This reset link is invalid or has expired"
    assert owner.get("/auth/me").status_code == 401
    assert anon.post("/auth/login", json={"email": "reset@example.com", "password": PASSWORD}).status_code == 401
    assert anon.post("/auth/login", json={"email": "reset@example.com", "password": "brand new secret"}).status_code == 200


def test_reset_email_in_the_users_language(make_client):
    mailbox = Mailbox()
    app.dependency_overrides[get_email] = lambda: mailbox
    c = make_client()
    c.post("/auth/register", json={"email": "nino@example.com", "password": PASSWORD, "full_name": "ნინო", "language": "ka"})
    make_client().post("/auth/password-reset", json={"email": "nino@example.com"})
    assert mailbox.sent[0][1] == "პაროლის აღდგენა" and "გამარჯობა, ნინო!" in mailbox.sent[0][2]


def test_reset_requests_are_limited(make_client):
    mailbox = Mailbox()
    app.dependency_overrides[get_email] = lambda: mailbox
    make_client("many@example.com")
    c = make_client()
    codes = [c.post("/auth/password-reset", json={"email": "many@example.com"}).status_code for _ in range(4)]
    assert codes == [202, 202, 202, 429] and len(mailbox.sent) == 3


def test_security_headers(make_client):
    c = make_client()
    page = c.get("/")
    assert page.headers["x-content-type-options"] == "nosniff"
    assert page.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert "strict-transport-security" not in page.headers  # only behind HTTPS
    assert "content-security-policy" not in c.get("/docs").headers  # Swagger UI loads from a CDN


def test_delete_account_needs_the_password_and_removes_everything(make_client):
    c = make_client("leaving@example.com")
    company = c.post("/companies", json={"name": "Bye LLC", "tax_id": "404000555", "legal_form": "LLC",
                                         "registration_date": "2024-01-01"}).json()
    c.post(f"/companies/{company['id']}/transactions", json={"occurred_on": "2026-09-01", "direction": "income", "amount": "5"})
    c.post(f"/companies/{company['id']}/chat", json={"message": "hello"})
    assert c.request("DELETE", "/auth/me", json={"password": "not it"}).status_code == 403
    assert c.request("DELETE", "/auth/me", json={"password": PASSWORD}).status_code == 204
    assert c.get("/auth/me").status_code == 401
    other = make_client()
    assert other.post("/auth/login", json={"email": "leaving@example.com", "password": PASSWORD}).status_code == 401
    # The address is free again, with nothing left over.
    again = make_client("leaving@example.com")
    assert again.get("/companies").json() == [] and again.get("/conversations").json() == []


def test_privacy_page(make_client):
    body = make_client().get("/privacy").text
    assert "კონფიდენციალურობის პოლიტიკა" in body and "Privacy policy" in body and "Draft." in body
