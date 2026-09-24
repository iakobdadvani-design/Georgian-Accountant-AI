"""Small business status (Tax Code Art. 88-90, 93): 1% of taxable income, 3% after GEL 500 000 in the year."""

from datetime import date
from decimal import Decimal

import pytest

from app.chat.extractor import KeywordExtractor
from app.rules.calendar import upcoming
from app.rules.engine import evaluate_rule
from app.rules.loader import get_rules

AS_OF = "2026-09-24"


def rule():
    return next(r for r in get_rules() if r.rule_id == "ge.small_business.tax")


def facts(**inputs):
    return {"company.legal_form": "IE", "company.tax_regime": "small_business",
            **{f"input.{k}": v for k, v in inputs.items()}}


@pytest.mark.parametrize("income, over, tax, after", [
    ("4000", False, "40.00", "3960.00"),
    ("4000", True, "120.00", "3880.00"),
    ("1234.56", False, "12.35", "1222.21"),  # 12.3456 rounds half-up
])
def test_worked_examples(income, over, tax, after):
    result = evaluate_rule(rule(), facts(small_business_income=income, over_small_business_limit=over))
    assert result.status == "applies" and result.verification == "unverified"
    assert result.amount == Decimal(tax)
    assert {line.name: line.amount for line in result.breakdown} == {"tax": Decimal(tax), "after_tax": Decimal(after)}


def test_only_for_individual_entrepreneurs():
    result = evaluate_rule(rule(), {**facts(small_business_income="4000", over_small_business_limit=False),
                                    "company.legal_form": "LLC"})
    assert result.status == "not_applicable"
    assert "Art. 88(1)" in result.reasons[0]["en"]


def test_needs_the_status():
    result = evaluate_rule(rule(), {**facts(small_business_income="4000", over_small_business_limit=False),
                                    "company.tax_regime": "standard"})
    assert result.status == "not_applicable"
    assert "Art. 89(1)" in result.reasons[0]["en"]


@pytest.mark.parametrize("message, entities", [
    ("I'm a small business, earned 4,000 this month", {"small_business_income": "4000"}),
    ("მცირე ბიზნესი ვარ, ამ თვეში 4000 ლარი გამოვიმუშავე", {"small_business_income": "4000"}),
    ("малый бизнес, доход 4 000 лари", {"small_business_income": "4000"}),
    ("Kleinunternehmer, 4.000 GEL Einnahmen", {"small_business_income": "4000"}),
    ("petite entreprise, revenu de 4 000 GEL", {"small_business_income": "4000"}),
    ("small business: this year I'm over 500,000, earned 20,000 this month",
     {"small_business_income": "20000", "over_small_business_limit": True}),
    ("მცირე ბიზნესი, შემოსავალმა 500 000 ლარს გადააჭარბა", {"over_small_business_limit": True}),
])
def test_keyword_extraction(message, entities):
    extraction = KeywordExtractor().extract(message)
    assert extraction.intent == "calculate_small_business_tax"
    assert extraction.entities == entities


@pytest.fixture
def entrepreneur(client):
    ie = client.post("/companies", json={
        "name": "Nino IE", "tax_id": "01001012345", "legal_form": "IE", "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{ie['id']}/tax-profile", json={"tax_regime": "small_business"})
    return ie


def chat(client, company, message):
    response = client.post(f"/companies/{company['id']}/chat", json={"message": message, "as_of": AS_OF})
    assert response.status_code == 200, response.text
    return response.json()


def test_chat_answer_first_with_assumption(client, entrepreneur):
    body = chat(client, entrepreneur, "small business, 4000 income this month")
    assert body["reply"].startswith("On 4,000 GEL of income you pay 40.00 GEL")
    assert "within GEL 500,000" in body["reply"]
    assert body["extraction"]["assumed"] == ["over_small_business_limit"]


def test_chat_georgian_over_limit(client, entrepreneur):
    body = chat(client, entrepreneur, "მცირე ბიზნესი: წლის შემოსავალი 500 000-ს გადააჭარბა, ამ თვეში 20000 ლარი")
    assert body["reply"].startswith("20 000 ლარის შემოსავალზე იხდით 600,00 ლარს")
    assert body["extraction"]["assumed"] == []


def test_chat_asks_for_income_then_accepts_a_bare_number(client, entrepreneur):
    first = chat(client, entrepreneur, "how much is small business tax?")
    assert first["reply"].startswith("As a small business you pay 1% of taxable income")
    body = client.post(f"/companies/{entrepreneur['id']}/chat", json={
        "message": "2500", "as_of": AS_OF, "conversation_id": first["conversation_id"]}).json()
    assert body["reply"].startswith("On 2,500 GEL of income you pay 25.00 GEL")


def test_chat_llc_is_told_why_not(client):
    llc = client.post("/companies", json={
        "name": "Tbilisi LLC", "tax_id": "404333333", "legal_form": "LLC", "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{llc['id']}/tax-profile", json={"tax_regime": "standard"})
    body = chat(client, llc, "small business tax on 4000")
    assert body["reply"].startswith("Small business status (1%) can only be granted to an individual entrepreneur")


def test_deadlines_follow_the_regime():
    small = {(o.deadline.deadline_id, o.due_date) for o in upcoming({"company.tax_regime": "small_business"},
                                                                    date(2026, 9, 24), months=1)}
    assert ("ge.small_business.monthly_return", date(2026, 10, 15)) in small
    micro = {(o.deadline.deadline_id, o.due_date, o.period_start.year)
             for o in upcoming({"company.tax_regime": "micro_business"}, date(2027, 1, 10), months=3)}
    assert micro == {("ge.micro_business.annual_return", date(2027, 3, 31), 2026)}
