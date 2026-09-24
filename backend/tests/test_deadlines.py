from datetime import date

import pytest

from app.chat.extractor import KeywordExtractor
from app.rules.calendar import load_deadlines, upcoming

TODAY = "2026-09-24"
ALL_FACTS = {"company.vat_registered": True, "company.has_employees": True, "company.legal_form": "LLC",
             "company.owns_property": True}


def test_shipped_deadlines_load_and_cite_the_tax_code():
    deadlines = load_deadlines()
    assert {d.deadline_id for d in deadlines} == {
        "ge.vat.monthly_return", "ge.withholding.monthly_return", "ge.profit.monthly_return",
        "ge.property.annual_return", "ge.property.current_payment"}
    assert all(d.legal_source.url and d.verification == "unverified" for d in deadlines)


def test_monthly_deadline_is_the_15th_after_the_period():
    [vat] = [o for o in upcoming(ALL_FACTS, date(2026, 9, 24), months=1) if o.deadline.deadline_id == "ge.vat.monthly_return"
             and o.due_date == date(2026, 10, 15)]
    assert (vat.period_start, vat.period_end) == (date(2026, 9, 1), date(2026, 9, 30))


def test_property_tax_dates():
    found = {(o.deadline.deadline_id, o.due_date, o.period_start.year)
             for o in upcoming(ALL_FACTS, date(2027, 1, 10), months=6) if o.deadline.tax_type == "property"}
    assert found == {("ge.property.annual_return", date(2027, 4, 1), 2026),
                     ("ge.property.current_payment", date(2027, 6, 15), 2027)}


@pytest.mark.parametrize("facts, expected", [
    ({"company.vat_registered": False, "company.has_employees": False, "company.legal_form": "IE",
      "company.owns_property": False}, set()),
    ({"company.vat_registered": True, "company.has_employees": False, "company.legal_form": "IE",
      "company.owns_property": False}, {"ge.vat.monthly_return"}),
    ({"company.vat_registered": False, "company.has_employees": True, "company.legal_form": "LLC",
      "company.owns_property": False}, {"ge.withholding.monthly_return", "ge.profit.monthly_return"}),
    ({"company.legal_form": "LLC"}, {"ge.profit.monthly_return"}),  # unknown facts don't create deadlines
])
def test_deadlines_follow_the_profile(facts, expected):
    assert {o.deadline.deadline_id for o in upcoming(facts, date(2026, 9, 24))} == expected


# --- API ---

@pytest.fixture
def company(client):
    company = client.post("/companies", json={
        "name": "Calendar LLC", "tax_id": "404999999", "legal_form": "LLC", "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile",
               json={"vat_registered": True, "has_employees": True, "owns_property": False})
    return company


def items(client, company, **params):
    response = client.get(f"/companies/{company['id']}/deadlines", params={"as_of": TODAY, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_list_marks_overdue_and_due_soon(client, company):
    listed = items(client, company)
    by_key = {i["key"]: i for i in listed}
    # August's returns were due on 15 September: overdue until marked done
    assert by_key["ge.vat.monthly_return:2026-08-01"]["state"] == "overdue"
    assert by_key["ge.vat.monthly_return:2026-08-01"]["days_left"] == -9
    assert by_key["ge.vat.monthly_return:2026-09-01"]["state"] == "upcoming"
    assert [i["due_date"] for i in listed] == sorted(i["due_date"] for i in listed)
    assert not any(i["tax_type"] == "property" for i in listed)
    # due soon inside a week
    soon = items(client, company, as_of="2026-10-10")
    assert {i["state"] for i in soon if i["due_date"] == "2026-10-15"} == {"due_soon"}


def test_mark_done_and_undo(client, company):
    url = f"/companies/{company['id']}/deadlines/ge.vat.monthly_return/2026-08-01"
    done = client.put(url, params={"as_of": TODAY}, json={"done": True})
    assert done.status_code == 200 and done.json()["state"] == "done"
    assert "ge.vat.monthly_return:2026-08-01" not in {i["key"] for i in items(client, company)}  # past + done
    undone = client.put(url, params={"as_of": TODAY}, json={"done": False})
    assert undone.json()["state"] == "overdue"


@pytest.mark.parametrize("path", [
    "ge.nope/2026-08-01",                      # unknown deadline
    "ge.property.annual_return/2026-01-01",    # doesn't apply: no property
    "ge.vat.monthly_return/2026-08-15",        # not a period start
])
def test_mark_done_rejects_invalid_occurrences(client, company, path):
    response = client.put(f"/companies/{company['id']}/deadlines/{path}", params={"as_of": TODAY}, json={"done": True})
    assert response.status_code == 404


def test_deadlines_are_private(client, company, make_client):
    intruder = make_client("cal-intruder@example.com")
    assert intruder.get(f"/companies/{company['id']}/deadlines").status_code == 404


def test_profile_round_trips_new_fields(client, company):
    profile = client.get(f"/companies/{company['id']}/tax-profile").json()
    assert profile["has_employees"] is True and profile["owns_property"] is False


# --- chat ---

def chat(client, company, message):
    response = client.post(f"/companies/{company['id']}/chat", json={"message": message, "as_of": TODAY})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("message", ["What's due?", "რა ვადები მაქვს?", "show my tax calendar"])
def test_deadline_intent(message):
    assert KeywordExtractor().extract(message).intent == "list_deadlines"


def test_due_does_not_steal_vat_amount_questions():
    assert KeywordExtractor().extract("How much VAT is in 11,800 GEL including VAT?").intent == "calculate_vat"


def test_chat_lists_deadlines_in_english(client, company):
    body = chat(client, company, "What's due?")
    assert body["reply"].startswith("Here's what's coming up:\n")
    assert "- VAT return and payment for August 2026: by 15 September 2026 (9 days overdue)" in body["reply"]
    assert "July 2026" not in body["reply"]  # older than the one-month look-back
    assert "- VAT return and payment for September 2026: by 15 October 2026 (in 21 days)" in body["reply"]
    assert "more in the coming months" in body["reply"]  # the chat lists the next 5
    assert body["deadlines"] and body["results"] == []


def test_chat_lists_deadlines_in_georgian(client, company):
    reply = chat(client, company, "რა ვადები მაქვს?")["reply"]
    assert reply.startswith("აი, რა ვადები გელით:\n")
    assert "- დღგ-ის დეკლარაცია და გადახდა (აგვისტო 2026): 15 სექტემბერი 2026-მდე (ვადა გადაცილებულია 9 დღით)" in reply


def test_chat_with_no_applicable_deadlines(client):
    ie = client.post("/companies", json={
        "name": "Solo IE", "tax_id": "01001011111", "legal_form": "IE", "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{ie['id']}/tax-profile", json={"vat_registered": False})
    assert chat(client, ie, "any deadlines?")["reply"].startswith("Based on the company's profile, no filing deadlines")
