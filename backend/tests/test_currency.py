"""Foreign-currency records: translated into lari at the NBG official rate for the day (Tax Code Art. 73(10))."""

import base64
import json
from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.nbg import NBGClient, NBGError


def nbg_with(responses: dict[str, list]):
    """An NBGClient whose HTTP answers come from `responses` (date -> JSON body); counts requests."""
    calls = []

    def handler(request: httpx.Request):
        day = request.url.params["date"]
        calls.append(day)
        return httpx.Response(200, content=json.dumps(responses.get(day, [])).encode())

    return NBGClient(httpx.Client(transport=httpx.MockTransport(handler))), calls


def block(day: str, code: str, rate: str, quantity: int = 1):
    return [{"date": f"{day}T00:00:00.000Z", "currencies": [
        {"code": code, "quantity": quantity, "rate": float(rate), "validFromDate": f"{day}T00:00:00.000Z"}]}]


def test_rate_for_the_day_per_unit_and_cached():
    client, calls = nbg_with({"2026-09-01": block("2026-09-01", "USD", "2.6156"),
                              "2026-09-02": block("2026-09-02", "JPY", "1.8123", quantity=100)})
    usd = client.rate("USD", date(2026, 9, 1))
    assert (usd.lari, usd.day) == (Decimal("2.6156"), date(2026, 9, 1))
    assert client.rate("JPY", date(2026, 9, 2)).lari == Decimal("0.018123")
    client.rate("USD", date(2026, 9, 1))
    assert calls == ["2026-09-01", "2026-09-02"]  # the second USD lookup came from the cache


def test_a_day_without_a_rate_takes_the_latest_before_it():
    client, calls = nbg_with({"2026-09-04": block("2026-09-04", "USD", "2.6200")})
    rate = client.rate("USD", date(2026, 9, 6))  # a Sunday: nothing on the 6th or 5th
    assert (rate.lari, rate.day) == (Decimal("2.6200"), date(2026, 9, 4))
    assert calls == ["2026-09-06", "2026-09-05", "2026-09-04"]


def test_no_rate_at_all_or_a_broken_service_is_an_error():
    client, _ = nbg_with({})
    with pytest.raises(NBGError):
        client.rate("USD", date(2026, 9, 6))
    broken = NBGClient(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    with pytest.raises(NBGError):
        broken.rate("USD", date(2026, 9, 6))


# --- the books ---

@pytest.fixture
def company(client):
    company = client.post("/companies", json={"name": "FX LLC", "tax_id": "404555555", "legal_form": "LLC",
                                              "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": True})
    return company


def add(client, company, **body):
    response = client.post(f"/companies/{company['id']}/transactions",
                           json={"occurred_on": "2026-09-01", "direction": "income", **body})
    assert response.status_code == 201, response.text
    return response.json()


def month(client, company):
    return client.get(f"/companies/{company['id']}/books", params={"month": "2026-09"}).json()["totals"]


def test_foreign_record_is_stored_with_its_rate_and_counted_in_lari(client, company):
    usd = add(client, company, amount="1000", currency="usd", vat_amount="152.54")
    assert (usd["currency"], usd["exchange_rate"], usd["rate_date"]) == ("USD", "2.700000", "2026-09-01")
    assert (usd["gel_amount"], usd["gel_vat_amount"]) == ("2700.00", "411.86")
    add(client, company, amount="500")  # lari
    totals = month(client, company)
    assert (totals["income"], totals["output_vat"], totals["count"], totals["unconverted"]) == ("3200.00", "411.86", 2, 0)


def test_records_saved_while_the_nbg_is_down_are_reported_then_converted(client, company, nbg):
    nbg.down = True
    usd = add(client, company, amount="1000", currency="USD")
    assert usd["gel_amount"] is None
    totals = month(client, company)
    assert (totals["income"], totals["unconverted"]) == ("0.00", 1)  # left out, and said so
    assert client.post(f"/companies/{company['id']}/books/convert").json() == {"converted": 0, "remaining": 1}
    nbg.down = False
    assert client.post(f"/companies/{company['id']}/books/convert").json() == {"converted": 1, "remaining": 0}
    assert month(client, company)["income"] == "2700.00"


def test_statement_import_takes_the_bank_accounts_currency(client, company):
    bank = client.post(f"/companies/{company['id']}/banks", json={"bank_id": "bog", "currency": "EUR"}).json()
    csv = "Date,Description,Amount\n2026-09-03,Invoice 7,200\n2026-09-04,Hosting,-50\n".encode()
    result = client.post(f"/companies/{company['id']}/books/import", json={
        "filename": "eur.csv", "content": base64.b64encode(csv).decode(), "bank_account_id": bank["id"]}).json()
    assert (result["imported"], result["unconverted"]) == (2, 0)
    records = client.get(f"/companies/{company['id']}/transactions").json()
    assert {(r["currency"], r["amount"], r["gel_amount"]) for r in records} == {("EUR", "200.00", "600.00"), ("EUR", "50.00", "150.00")}
    totals = month(client, company)
    assert (totals["income"], totals["expense"]) == ("600.00", "150.00")


@pytest.mark.parametrize("currency", ["US", "US$", "1234"])
def test_currency_must_be_a_three_letter_code(client, company, currency):
    response = client.post(f"/companies/{company['id']}/transactions",
                           json={"occurred_on": "2026-09-01", "direction": "income", "amount": "10", "currency": currency})
    assert response.status_code == 422
