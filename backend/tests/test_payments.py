"""Paying a tax from the customer's own bank: treasury details, the amount from the books, and marking it paid."""

import pytest

TODAY = "2026-09-24"


@pytest.fixture
def company(client):
    company = client.post("/companies", json={
        "name": "Pay LLC", "tax_id": "404888888", "legal_form": "LLC", "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": True, "has_employees": True})
    return company


def items(client, company):
    return {i["key"]: i for i in client.get(f"/companies/{company['id']}/deadlines", params={"as_of": TODAY}).json()}


def test_payment_details_are_one_treasury_code():
    from fastapi.testclient import TestClient
    from app.main import app
    details = TestClient(app).get("/payments").json()
    assert (details["treasury_code"], details["bank_code"]) == ("101001000", "TRESGE22")
    assert {"tbc", "bog"} <= {b["id"] for b in details["banks"]}
    assert all(b["url"].startswith("https://") for b in details["banks"])


def test_vat_amount_due_comes_from_the_recorded_month(client, company):
    assert items(client, company)["ge.vat.monthly_return:2026-08-01"]["amount_due"] is None  # nothing recorded
    for body in ({"occurred_on": "2026-08-10", "direction": "income", "amount": "11800", "vat_amount": "1800"},
                 {"occurred_on": "2026-08-20", "direction": "expense", "amount": "5900", "vat_amount": "900"}):
        assert client.post(f"/companies/{company['id']}/transactions", json=body).status_code == 201
    listed = items(client, company)
    assert listed["ge.vat.monthly_return:2026-08-01"]["amount_due"] == "900.00"  # 1 800 output - 900 input
    assert listed["ge.vat.monthly_return:2026-08-01"]["payment"] is True
    assert listed["ge.withholding.monthly_return:2026-08-01"]["amount_due"] is None  # payroll isn't in the books


def test_mark_paid_records_the_amount_and_undo_clears_it(client, company):
    url = f"/companies/{company['id']}/deadlines/ge.vat.monthly_return/2026-09-01"
    paid = client.put(url, params={"as_of": TODAY}, json={"done": True, "paid_amount": "900.00"}).json()
    assert (paid["state"], paid["paid_amount"], paid["amount_due"]) == ("done", "900.00", None)
    filed = client.put(url, params={"as_of": TODAY}, json={"done": True}).json()
    assert (filed["state"], filed["paid_amount"]) == ("done", None)
    undone = client.put(url, params={"as_of": TODAY}, json={"done": False}).json()
    assert (undone["state"], undone["paid_amount"]) == ("upcoming", None)


@pytest.mark.parametrize("body", [{"done": False, "paid_amount": "10"}, {"done": True, "paid_amount": "-1"},
                                  {"done": True, "paid_amount": "1.234"}])
def test_bad_paid_amounts_are_refused(client, company, body):
    url = f"/companies/{company['id']}/deadlines/ge.vat.monthly_return/2026-09-01"
    assert client.put(url, params={"as_of": TODAY}, json=body).status_code == 422


def test_micro_business_return_has_nothing_to_pay(client):
    ie = client.post("/companies", json={
        "name": "Micro", "tax_id": "01001000002", "legal_form": "IE", "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{ie['id']}/tax-profile", json={"tax_regime": "micro_business"})
    [item] = client.get(f"/companies/{ie['id']}/deadlines", params={"as_of": "2027-03-01"}).json()
    assert (item["deadline_id"], item["payment"]) == ("ge.micro_business.annual_return", False)
    url = f"/companies/{ie['id']}/deadlines/ge.micro_business.annual_return/2026-01-01"
    assert client.put(url, params={"as_of": "2027-03-01"}, json={"done": True, "paid_amount": "5"}).status_code == 422


IBAN = "GE74TB1234567890123456"  # valid check digits (ISO 13616), made up


def test_save_change_and_remove_the_bank(client, company):
    url = f"/companies/{company['id']}/bank"
    assert client.get(url).json() is None
    saved = client.put(url, json={"bank_id": "tbc", "iban": " ge74 tb12 3456 7890 1234 56 "})
    assert saved.status_code == 200 and saved.json() == {"bank_id": "tbc", "iban": IBAN}
    assert client.put(url, json={"bank_id": "bog", "iban": ""}).json() == {"bank_id": "bog", "iban": None}
    assert client.get(url).json()["bank_id"] == "bog"
    assert client.delete(url).status_code == 204
    assert client.get(url).json() is None and client.delete(url).status_code == 404


@pytest.mark.parametrize("body", [{"bank_id": "nope"}, {"bank_id": "tbc", "iban": "GE72TB1234567890123456"},
                                  {"bank_id": "tbc", "iban": "DE89370400440532013000"}])
def test_bad_bank_choices_are_refused(client, company, body):
    assert client.put(f"/companies/{company['id']}/bank", json=body).status_code == 422


def test_bank_is_private(client, company, make_client):
    client.put(f"/companies/{company['id']}/bank", json={"bank_id": "tbc"})
    assert make_client("pay-intruder@example.com").get(f"/companies/{company['id']}/bank").status_code == 404


def test_history_lists_paid_taxes_newest_first(client, company):
    base = f"/companies/{company['id']}/deadlines"
    client.put(f"{base}/ge.vat.monthly_return/2026-08-01", params={"as_of": TODAY},
               json={"done": True, "paid_amount": "900", "paid_on": "2026-09-14"})
    client.put(f"{base}/ge.withholding.monthly_return/2026-08-01", params={"as_of": TODAY},
               json={"done": True, "paid_amount": "400"})
    client.put(f"{base}/ge.profit.monthly_return/2026-08-01", params={"as_of": TODAY}, json={"done": True})  # filed only
    history = client.get(f"/companies/{company['id']}/payments/history").json()
    assert [(h["deadline_id"], h["amount"], h["paid_on"]) for h in history] == [
        ("ge.withholding.monthly_return", "400.00", TODAY), ("ge.vat.monthly_return", "900.00", "2026-09-14")]
    assert history[0]["title"]["en"]
