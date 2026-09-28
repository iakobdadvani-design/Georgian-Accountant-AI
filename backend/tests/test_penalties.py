"""Late payment interest (Tax Code Art. 272) and the fine for filing late (Art. 274), worked examples."""

from datetime import date
from decimal import Decimal

import pytest

from app.chat.extractor import KeywordExtractor
from app.rules.engine import evaluate
from app.rules.lateness import lateness
from app.rules.loader import get_rules

ON = date(2026, 9, 28)


def run(rule_id: str, **facts):
    rules = [r for r in get_rules() if r.rule_id == rule_id]
    [result] = evaluate(rules, {f"input.{k}": v for k, v in facts.items()}, ON)
    return result


@pytest.mark.parametrize("due, done, days, months", [
    (date(2026, 9, 15), date(2026, 9, 15), 0, 0),    # on the day: on time
    (date(2026, 9, 15), date(2026, 9, 16), 1, 1),    # the day of payment counts (272(4))
    (date(2026, 9, 15), date(2026, 10, 15), 30, 1),  # exactly one month
    (date(2026, 9, 15), date(2026, 10, 16), 31, 2),  # into the second month
    (date(2026, 9, 15), date(2026, 11, 15), 61, 2),  # exactly two months: still "up to 2 months"
    (date(2026, 9, 15), date(2026, 11, 16), 62, 3),  # more than two months
    (date(2026, 1, 31), date(2026, 2, 28), 28, 1),   # month ends are clamped
])
def test_lateness(due, done, days, months):
    late = lateness(due, done)
    assert (late.days, late.months) == (days, months)


def test_interest_is_0_05_percent_a_day():
    r = run("ge.penalty.late_payment", tax_due="2000", days_late=20)
    assert (r.status, r.amount) == ("applies", Decimal("20.00"))  # 2 000 x 20 x 0.0005
    assert {b.name: b.amount for b in r.breakdown}["total"] == Decimal("2020.00")


def test_interest_stops_after_three_years():
    r = run("ge.penalty.late_payment", tax_due="1000", days_late=1500)
    assert r.amount == Decimal("547.50")  # 1 095 days, not 1 500


@pytest.mark.parametrize("facts", [{"tax_due": "0", "days_late": 10}, {"tax_due": "500", "days_late": 0}])
def test_no_interest_without_unpaid_tax_or_delay(facts):
    r = run("ge.penalty.late_payment", **facts)
    assert r.status == "not_applicable" and r.reasons


@pytest.mark.parametrize("months, fine", [(1, "50.00"), (2, "100.00"), (3, "100.00"), (14, "100.00")])
def test_late_filing_fine(months, fine):
    r = run("ge.penalty.late_filing", tax_due="1000", months_late=months)
    assert (r.status, r.amount) == ("applies", Decimal(fine))


def test_no_filing_fine_when_the_tax_is_zero():
    r = run("ge.penalty.late_filing", tax_due="0", months_late=2)
    assert r.status == "not_applicable" and "274(3)" in r.reasons[0]["en"]


def test_overdue_deadline_shows_what_paying_and_filing_today_would_cost(client):
    company = client.post("/companies", json={"name": "Late LLC", "tax_id": "404333333", "legal_form": "LLC",
                                              "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": True})
    for body in ({"occurred_on": "2026-08-10", "direction": "income", "amount": "11800", "vat_amount": "1800"},
                 {"occurred_on": "2026-08-20", "direction": "expense", "amount": "5900", "vat_amount": "900"}):
        client.post(f"/companies/{company['id']}/transactions", json=body)
    items = {i["key"]: i for i in client.get(f"/companies/{company['id']}/deadlines", params={"as_of": "2026-09-24"}).json()}
    vat = items["ge.vat.monthly_return:2026-08-01"]
    assert (vat["state"], vat["amount_due"]) == ("overdue", "900.00")
    # due 15 Sep, today 24 Sep: 9 days (900 x 9 x 0.05% = 4.05) and the first started month (5% = 45.00)
    assert {p["rule_id"]: p["amount"] for p in vat["penalties"]} == {
        "ge.penalty.late_payment": "4.05", "ge.penalty.late_filing": "45.00"}
    assert items["ge.profit.monthly_return:2026-08-01"]["penalties"] == []  # amount unknown: nothing to compute on
    assert items["ge.vat.monthly_return:2026-09-01"]["penalties"] == []     # not due yet


@pytest.mark.parametrize("message, entities", [
    ("I paid 2,000 GEL of VAT 20 days late, what is the penalty?", {"tax_due": "2000", "days_late": "20"}),
    ("დღგ 3000 ლარი 10 დღით გვიან გადავიხადე, რამდენია საურავი?", {"tax_due": "3000", "days_late": "10"}),
    ("Заплатил налог 5 000 лари с опозданием на 30 дней", {"tax_due": "5000", "days_late": "30"}),
    ("1.000 GEL Steuer 45 Tage zu spät gezahlt", {"tax_due": "1000", "days_late": "45"}),
    ("4 000 GEL d'impôt payé avec 12 jours de retard", {"tax_due": "4000", "days_late": "12"}),
    ("VAT return filed 3 months late, tax 1,000", {"tax_due": "1000", "months_late": "3"}),
    ("what's the penalty for paying late?", {}),
])
def test_keyword_extraction(message, entities):
    extraction = KeywordExtractor().extract(message)
    assert (extraction.intent, extraction.entities) == ("calculate_late_penalty", entities)


def chat(client, company, message, conversation=None):
    response = client.post(f"/companies/{company['id']}/chat", json={
        "message": message, "as_of": "2026-09-28", "conversation_id": conversation})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def company(client):
    return client.post("/companies", json={"name": "Late LLC", "tax_id": "404333334", "legal_form": "LLC",
                                           "registration_date": "2024-01-01"}).json()


def test_chat_answers_interest_and_fine(client, company):
    body = chat(client, company, "I paid 2,000 GEL of VAT 20 days late, what is the penalty?")
    # 20 days before 28 Sep is 8 Sep: the delay started one month, so the filing fine is 5%
    assert body["reply"].startswith("Penalty interest is 20.00 GEL: 0.05% of 2,000 GEL for each overdue day "
                                    "(20 days overdue), so 2,020.00 GEL in all.")
    assert "add a fine of 100.00 GEL" in body["reply"]
    assert body["extraction"]["entities"]["months_late"] == "1"


def test_chat_in_georgian(client, company):
    body = chat(client, company, "დღგ 3000 ლარი 10 დღით გვიან გადავიხადე, რამდენია საურავი?")
    assert body["reply"].startswith("საურავი 15,00 ლარია")


def test_chat_asks_then_takes_a_bare_number_of_days(client, company):
    first = chat(client, company, "I paid 1,000 GEL of tax late, what's the penalty?")
    assert first["reply"].startswith("How many days late is the payment of 1,000 GEL?")
    body = chat(client, company, "15", first["conversation_id"])
    assert body["reply"].startswith("Penalty interest is 7.50 GEL")


def test_chat_months_only_gives_the_fine_and_asks_for_days(client, company):
    body = chat(client, company, "We filed the VAT return 3 months late, tax was 1,000 GEL. What fine?")
    assert body["reply"].startswith("The fine for filing the return late is 100.00 GEL")


def test_chat_general_question_explains_and_asks(client, company):
    body = chat(client, company, "what's the penalty for paying late?")
    assert body["reply"].startswith("Paying late costs 0.05% of the unpaid tax for each day")


def test_missing_facts_are_asked_for():
    r = run("ge.penalty.late_payment", tax_due="1000")
    assert (r.status, r.missing_facts) == ("insufficient_data", ["input.days_late"])
