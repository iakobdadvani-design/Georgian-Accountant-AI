"""Recording sales and expenses from the chat: a draft to confirm, never a write without the user's Save."""

import pytest

from app.chat.extractor import KeywordExtractor
from app.chat.records import direction_of, record_entities

AS_OF = "2026-09-29"


@pytest.mark.parametrize("message, entities", [
    ("Record a sale of 1,000 GEL today", {"record_amount": "1000", "record_direction": "income", "record_date": "today"}),
    ("ჩაწერე ხარჯი 150 ლარი ქირა გუშინ", {"record_amount": "150", "record_direction": "expense", "record_date": "yesterday"}),
    ("Запиши продажу 500 долларов 25.09.2026",
     {"record_amount": "500", "record_direction": "income", "record_currency": "USD", "record_date": "2026-09-25"}),
    ("Trage eine Ausgabe von 80 EUR ein", {"record_amount": "80", "record_direction": "expense", "record_currency": "EUR"}),
    ("Enregistre une vente de 2 000 GEL", {"record_amount": "2000", "record_direction": "income"}),
    ("add expense: paid 12.50 for coffee", {"record_amount": "12.50", "record_direction": "expense"}),
    ("record 300 GEL", {"record_amount": "300"}),
])
def test_keyword_extraction(message, entities):
    extraction = KeywordExtractor().extract(message)
    assert (extraction.intent, extraction.entities) == ("record_transaction", entities)


@pytest.mark.parametrize("message, direction", [
    ("I got paid 700 USD", "income"), ("paid 150 for internet", "expense"), ("received and paid", None), ("500", None),
])
def test_direction(message, direction):
    assert direction_of(message) == direction


def test_invalid_dates_are_ignored():
    assert "record_date" not in record_entities("record a sale of 100 on 31.02.2026")


@pytest.fixture
def company(client):
    company = client.post("/companies", json={"name": "Rec LLC", "tax_id": "404222222", "legal_form": "LLC",
                                              "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": True})
    return company


def chat(client, company, message, conversation=None):
    response = client.post(f"/companies/{company['id']}/chat", json={
        "message": message, "as_of": AS_OF, "conversation_id": conversation})
    assert response.status_code == 200, response.text
    return response.json()


def test_chat_drafts_but_does_not_save(client, company):
    body = chat(client, company, "Record a sale of 1,000 GEL yesterday")
    assert body["draft"] == {"occurred_on": "2026-09-28", "direction": "income", "amount": "1000", "currency": "GEL",
                             "vat_included": True, "vat_payer": True, "description": "Record a sale of 1,000 GEL yesterday",
                             "date_assumed": False}
    assert body["reply"].startswith("I'll record a sale: 1,000 GEL on 28 September 2026.")
    assert body["results"] == []
    assert client.get(f"/companies/{company['id']}/transactions").json() == []  # nothing until Save


def test_chat_asks_for_what_is_missing_then_completes(client, company):
    first = chat(client, company, "ჩაწერე 250 ლარი")
    assert first["draft"] is None and first["reply"] == "ეს გაყიდვაა (შემოსავალი) თუ ხარჯი (გასავალი)?"
    body = chat(client, company, "ხარჯი", first["conversation_id"])
    assert (body["draft"]["direction"], body["draft"]["amount"], body["draft"]["date_assumed"]) == ("expense", "250", True)
    assert "დღევანდელი" in body["reply"]


def test_chat_amount_follow_up_and_foreign_currency(client, company):
    first = chat(client, company, "record an expense in dollars")
    assert first["reply"] == "How much was it?"
    body = chat(client, company, "80", first["conversation_id"])
    assert (body["draft"]["currency"], body["draft"]["amount"]) == ("USD", "80")
    assert "official rate" in body["reply"]


def test_nothing_to_record(client, company):
    assert chat(client, company, "record")["reply"].startswith("What should I record?")
