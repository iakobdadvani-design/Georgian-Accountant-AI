"""VAT payable after input VAT credit (Tax Code Art. 174-176, 181(1))."""

from decimal import Decimal

import pytest

from app.chat.extractor import KeywordExtractor, vat_amounts
from app.rules.engine import evaluate_rule
from app.rules.loader import get_rules

AS_OF = "2026-09-24"


def rule():
    return next(r for r in get_rules() if r.rule_id == "ge.vat.payable")


@pytest.mark.parametrize("output, input_, payable, excess", [
    ("18000", "9000", "9000.00", "0.00"),
    ("5000", "7250.50", "0.00", "2250.50"),
    ("3000", "3000", "0.00", "0.00"),
])
def test_worked_examples(output, input_, payable, excess):
    result = evaluate_rule(rule(), {"company.vat_registered": True, "input.output_vat": output, "input.input_vat": input_})
    assert result.status == "applies" and result.verification == "unverified"
    assert result.amount == Decimal(payable)
    assert {line.name: line.amount for line in result.breakdown} == {
        "payable": Decimal(payable), "excess_credit": Decimal(excess)}
    assert any(line.startswith("payable = max(") for line in result.trace)


def test_not_registered_cannot_deduct():
    result = evaluate_rule(rule(), {"company.vat_registered": False, "input.output_vat": "1", "input.input_vat": "1"})
    assert result.status == "not_applicable" and "174(3)" in result.reasons[0]["en"]


@pytest.mark.parametrize("message, expected", [
    ("VAT on sales 18,000 and input VAT on purchases 9,000", {"output_vat": "18000", "input_vat": "9000"}),
    ("input VAT 9,000, output VAT 18,000", {"output_vat": "18000", "input_vat": "9000"}),
    ("გაყიდვებზე დღგ 18 000, შესყიდვებზე ჩასათვლელი 9 000", {"output_vat": "18000", "input_vat": "9000"}),
    ("НДС с продаж 18 000, входящий НДС 9 000", {"output_vat": "18000", "input_vat": "9000"}),
    ("Umsatzsteuer 18.000, Vorsteuer 9.000", {"output_vat": "18000", "input_vat": "9000"}),
    ("TVA collectée 18 000, TVA déductible 9 000", {"output_vat": "18000", "input_vat": "9000"}),
    ("deductible VAT 4,000", {"input_vat": "4000"}),
    ("18000 and 9000", {"output_vat": "18000", "input_vat": "9000"}),
])
def test_amounts_are_told_apart(message, expected):
    assert vat_amounts(message) == expected


def test_keyword_intent():
    extraction = KeywordExtractor().extract("How much VAT do I pay after input VAT? Sales VAT 18,000, input VAT 9,000")
    assert extraction.intent == "calculate_vat_payable"
    assert extraction.entities == {"output_vat": "18000", "input_vat": "9000"}


@pytest.fixture
def registered(client):
    company = client.post("/companies", json={
        "name": "VAT LLC", "tax_id": "404666666", "legal_form": "LLC", "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": True})
    return company


def chat(client, company, message, conversation_id=None):
    response = client.post(f"/companies/{company['id']}/chat", json={
        "message": message, "as_of": AS_OF, "conversation_id": conversation_id})
    assert response.status_code == 200, response.text
    return response.json()


def test_chat_payable(client, registered):
    body = chat(client, registered, "VAT on sales 18,000 and input VAT on purchases 9,000")
    assert body["reply"].startswith("You pay 9,000.00 GEL VAT for the month: 18,000 GEL charged on sales minus 9,000 GEL")


def test_chat_refund_in_georgian(client, registered):
    body = chat(client, registered, "გაყიდვებზე დღგ 5000, შესყიდვებზე ჩასათვლელი დღგ 7000")
    assert body["reply"].startswith("ამ თვეში დღგ-ის გადახდა არ გიწევთ")
    assert "2 000,00 ლარის სხვაობის დაბრუნება" in body["reply"]


def test_chat_asks_for_both_amounts_in_turn(client, registered):
    first = chat(client, registered, "how much VAT do I pay after the input VAT credit?")
    assert first["reply"].startswith("Sure. VAT payable is the VAT you charged on sales")
    second = chat(client, registered, "18000", first["conversation_id"])
    assert second["reply"].startswith("Got it: 18,000 GEL VAT on sales.")
    third = chat(client, registered, "9000", first["conversation_id"])
    assert third["reply"].startswith("You pay 9,000.00 GEL VAT for the month")


def test_chat_not_registered(client):
    company = client.post("/companies", json={
        "name": "Small LLC", "tax_id": "404777777", "legal_form": "LLC", "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": False})
    body = chat(client, company, "input VAT 500, output VAT 900")
    assert body["reply"].startswith("You can't deduct VAT. Only a person registered as a VAT payer")
