"""Accountant sign-off: only listed reviewers decide, approvals follow the exact content, results show them."""

import pytest

from app.config import settings
from app.rules import loader
from app.rules.loader import get_rules

REVIEWER = "accountant@example.com"


@pytest.fixture
def reviewer(make_client, monkeypatch):
    monkeypatch.setattr(settings, "reviewer_emails", f"someone@example.com, {REVIEWER.upper()}")
    return make_client(REVIEWER)


def item(client, kind, item_id):
    return next(i for i in client.get("/reviews").json()["items"] if (i["kind"], i["item_id"]) == (kind, item_id))


def approve(client, kind, item_id, decision="approved", version=1, content_hash=None):
    current = item(client, kind, item_id)
    return client.post(f"/reviews/{kind}/{item_id}/{version}", json={
        "decision": decision, "credentials": "Certified accountant, No 123", "notes": "Checked against Matsne",
        "content_hash": content_hash or current["content_hash"]})


def test_list_shows_every_real_rule_and_deadline_unverified(client):
    body = client.get("/reviews").json()
    assert body["can_review"] is False
    kinds = {(i["kind"], i["item_id"]) for i in body["items"]}
    assert ("rule", "ge.vat.registration_threshold") in kinds and ("deadline", "ge.vat.monthly_return") in kinds
    assert not any(r.is_demo and ("rule", r.rule_id) in kinds for r in get_rules())
    assert {i["status"] for i in body["items"]} == {"unverified"}


def test_only_reviewers_can_decide(client, reviewer):
    assert approve(client, "rule", "ge.vat.payable").status_code == 403
    assert reviewer.get("/auth/me").json()["is_reviewer"] is True
    response = approve(reviewer, "rule", "ge.vat.payable")
    assert response.status_code == 201
    assert response.json()["status"] == "verified"
    assert response.json()["history"][0]["reviewer_credentials"] == "Certified accountant, No 123"


def test_stale_content_is_refused(reviewer):
    assert approve(reviewer, "rule", "ge.vat.payable", content_hash="0" * 64).status_code == 409
    assert reviewer.post("/reviews/rule/ge.unknown/1", json={
        "decision": "approved", "credentials": "x" * 5, "content_hash": "0" * 64}).status_code == 404


def test_approval_marks_chat_results_verified(client, reviewer):
    approve(reviewer, "rule", "ge.vat.registration_threshold")
    company = client.post("/companies", json={"name": "R", "tax_id": "404000777", "legal_form": "LLC",
                                              "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": False})
    body = client.post(f"/companies/{company['id']}/chat", json={"message": "our turnover is 50,000"}).json()
    [result] = body["results"]
    assert result["verification"] == "verified"
    assert result["reviewed_by"] == "Test, Certified accountant, No 123"
    assert "hasn't been reviewed" not in body["reply"]


def test_changes_requested_keeps_it_unverified(reviewer):
    approve(reviewer, "rule", "ge.vat.payable")
    response = approve(reviewer, "rule", "ge.vat.payable", decision="changes_requested")
    assert response.json()["status"] == "changes_requested"
    assert [h["decision"] for h in response.json()["history"]] == ["changes_requested", "approved"]


def test_editing_a_rule_after_approval_makes_it_outdated(reviewer, monkeypatch):
    approve(reviewer, "rule", "ge.vat.payable")
    edited = [r.model_copy(update={"message": "changed"}) if r.rule_id == "ge.vat.payable" else r for r in get_rules()]
    monkeypatch.setattr(loader, "get_rules", lambda: edited)
    monkeypatch.setattr("app.api.reviews.get_rules", lambda: edited)
    assert item(reviewer, "rule", "ge.vat.payable")["status"] == "outdated"


def test_deadline_approval_shows_in_calendar(client, reviewer):
    approve(reviewer, "deadline", "ge.vat.monthly_return")
    company = client.post("/companies", json={"name": "D", "tax_id": "404000778", "legal_form": "LLC",
                                              "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": True})
    items = client.get(f"/companies/{company['id']}/deadlines", params={"as_of": "2026-09-24"}).json()
    vat = [i for i in items if i["deadline_id"] == "ge.vat.monthly_return"]
    assert vat and all(i["verification"] == "verified" and i["reviewed_by"] for i in vat)
    others = [i for i in items if i["deadline_id"] != "ge.vat.monthly_return"]
    assert all(i["verification"] == "unverified" for i in others)
