"""Hiring from the chat and the monthly salary figures: take-home -> gross by rule, a card to confirm, the employee list."""

from datetime import date
from decimal import Decimal

import pytest

from app.chat.extractor import KeywordExtractor
from app.rules.engine import evaluate
from app.rules.loader import get_rules

AS_OF = "2026-09-29"


def gross_from_net(net: str, pension: bool):
    rules = [r for r in get_rules() if r.rule_id == "ge.payroll.gross_from_net"]
    [result] = evaluate(rules, {"input.net_salary": net, "input.pension_participant": pension}, date(2026, 9, 29))
    return result


def test_take_home_to_gross_in_the_pension_scheme():
    # 2 500 / 0.784 = 3 188.7755 -> 3 188.78; pension 2% 63.78; tax 20% of 3 125.00 = 625.00; take-home 2 500.00
    result = gross_from_net("2500", True)
    assert result.status == "applies" and result.amount == Decimal("3188.78")
    assert {b.name: b.amount for b in result.breakdown} == {
        "gross_salary": Decimal("3188.78"), "employee_pension": Decimal("63.78"), "income_tax": Decimal("625.00"),
        "net_salary": Decimal("2500.00"), "employer_pension": Decimal("63.78"), "employer_cost": Decimal("3252.56")}


def test_take_home_to_gross_outside_the_scheme():
    result = gross_from_net("2500", False)
    values = {b.name: b.amount for b in result.breakdown}
    assert values["gross_salary"] == Decimal("3125.00") and values["income_tax"] == Decimal("625.00")
    assert values["net_salary"] == Decimal("2500.00") and values["employer_cost"] == Decimal("3125.00")


def test_gross_round_trips_through_the_payroll_rule():
    gross = gross_from_net("1234.56", True).amount
    rules = [r for r in get_rules() if r.rule_id == "ge.payroll.income_tax"]
    [forward] = evaluate(rules, {"input.gross_salary": str(gross), "input.pension_participant": True}, date(2026, 9, 29))
    net = next(b.amount for b in forward.breakdown if b.name == "net_salary")
    assert abs(net - Decimal("1234.56")) <= Decimal("0.01")


@pytest.mark.parametrize("message, entities", [
    ("I hired someone for this company and I am paying 2500 lari on hand", {"net_salary": "2500", "hire": True}),
    ("დავიქირავე თანამშრომელი, ხელზე 2500 ლარი", {"net_salary": "2500", "hire": True}),
    ("Нанял сотрудника, 2500 лари на руки", {"net_salary": "2500", "hire": True}),
    ("Ich habe einen Mitarbeiter eingestellt, 2500 GEL netto", {"net_salary": "2500", "hire": True}),
    ("J'ai embauché un employé, 2 500 GEL net", {"net_salary": "2500", "hire": True}),
    ("What is the tax on a salary of 2500?", {"gross_salary": "2500"}),
    ("We hired a developer, gross salary 4000", {"gross_salary": "4000", "hire": True}),
    ("take-home pay of 1800, what does the salary cost the company?", {"net_salary": "1800"}),
])
def test_extraction(message, entities):
    extraction = KeywordExtractor().extract(message)
    assert (extraction.intent, extraction.entities) == ("calculate_payroll_tax", entities)


@pytest.fixture
def company(client):
    return client.post("/companies", json={"name": "Hire LLC", "tax_id": "404333333", "legal_form": "LLC",
                                           "registration_date": "2024-01-01"}).json()


def chat(client, company, message, conversation=None):
    response = client.post(f"/companies/{company['id']}/chat", json={
        "message": message, "as_of": AS_OF, "conversation_id": conversation})
    assert response.status_code == 200, response.text
    return response.json()


def test_hiring_from_the_chat_drafts_an_employee(client, company):
    body = chat(client, company, "I hired someone for this company and I am paying 2500 lari on hand")
    assert body["reply"].startswith("To pay 2,500.00 GEL on hand, the gross salary is 3,188.78 GEL.")
    assert "employee card below" in body["reply"]
    assert body["employee_draft"] == {"gross_monthly_salary": "3188.78", "net_monthly_salary": "2500",
                                      "pension_participant": True, "hired_on": AS_OF, "date_assumed": True}
    assert [r["rule_id"] for r in body["results"]] == ["ge.payroll.gross_from_net"]
    assert client.get(f"/companies/{company['id']}/employees").json() == []  # nothing until Save


def test_a_plain_salary_question_offers_no_card(client, company):
    body = chat(client, company, "What is the tax on a salary of 2500?")
    assert body["employee_draft"] is None and body["reply"].startswith("For a gross salary of 2,500 GEL")


def test_take_home_amount_as_a_follow_up(client, company):
    first = chat(client, company, "I hired a new employee")
    assert first["employee_draft"] is None and first["reply"].startswith("Sure, I can work that out.")
    second = chat(client, company, "2500 on hand", first["conversation_id"])
    assert second["used_context"] is True
    assert second["employee_draft"]["gross_monthly_salary"] == "3188.78"


def test_georgian_reply(client, company):
    body = chat(client, company, "დავიქირავე თანამშრომელი, ხელზე 2500 ლარი")
    assert body["reply"].startswith("ხელზე 2\xa0500,00 ლარის მისაცემად დარიცხული ხელფასი უნდა იყოს 3\xa0188,78 ლარი.")


EMPLOYEE = {"full_name": "Nino Beridze", "personal_id": "01001012345", "gross_monthly_salary": "3188.78",
            "pension_participant": True, "hired_on": "2026-09-01"}


def test_employee_list_and_monthly_figures(client, company):
    base = f"/companies/{company['id']}"
    added = client.post(f"{base}/employees", json=EMPLOYEE)
    assert added.status_code == 201, added.text
    assert client.post(f"{base}/employees", json=EMPLOYEE).status_code == 409  # same personal number
    client.post(f"{base}/employees", json={**EMPLOYEE, "full_name": "Giorgi", "personal_id": "01001054321",
                                           "gross_monthly_salary": "1000", "pension_participant": False,
                                           "hired_on": "2026-01-01", "terminated_on": "2026-08-31"})

    month = client.get(f"{base}/payroll", params={"month": "2026-09-15"}).json()
    assert [line["employee"]["full_name"] for line in month["lines"]] == ["Nino Beridze"]  # Giorgi left in August
    assert month["totals"]["income_tax"] == "625.00" and month["totals"]["net_salary"] == "2500.00"
    assert month["return_due"] == "2026-10-15"

    august = client.get(f"{base}/payroll", params={"month": "2026-08-01"}).json()
    assert [line["employee"]["full_name"] for line in august["lines"]] == ["Giorgi"]
    assert august["totals"]["income_tax"] == "200.00" and "employee_pension" in august["totals"]

    assert month["totals"]["gross_salary"] == "3188.78"

    # Having employees puts the withholding return on the calendar, for the months someone was employed.
    deadlines = client.get(f"{base}/deadlines", params={"as_of": AS_OF}).json()
    returns = [d["period_start"] for d in deadlines if d["deadline_id"] == "ge.withholding.monthly_return"]
    assert "2026-08-01" in returns and "2026-09-01" in returns


def test_no_salary_return_for_months_before_the_first_hire(client, company):
    base = f"/companies/{company['id']}"
    client.post(f"{base}/employees", json=EMPLOYEE)  # hired 1 September 2026
    deadlines = client.get(f"{base}/deadlines", params={"as_of": AS_OF}).json()
    returns = [d["period_start"] for d in deadlines if d["deadline_id"] == "ge.withholding.monthly_return"]
    assert "2026-08-01" not in returns and "2026-09-01" in returns


def test_employee_validation_and_edits(client, company):
    base = f"/companies/{company['id']}"
    assert client.post(f"{base}/employees", json={**EMPLOYEE, "personal_id": "12"}).status_code == 422
    assert client.post(f"{base}/employees", json={**EMPLOYEE, "gross_monthly_salary": "0"}).status_code == 422
    assert client.post(f"{base}/employees", json={**EMPLOYEE, "terminated_on": "2026-08-01"}).status_code == 422
    employee = client.post(f"{base}/employees", json=EMPLOYEE).json()
    updated = client.put(f"{base}/employees/{employee['id']}", json={**EMPLOYEE, "terminated_on": "2026-12-31"})
    assert updated.json()["terminated_on"] == "2026-12-31"
    assert client.delete(f"{base}/employees/{employee['id']}").status_code == 204
    assert client.get(f"{base}/employees").json() == []


def test_employees_are_private(client, make_client, company):
    employee = client.post(f"/companies/{company['id']}/employees", json=EMPLOYEE).json()
    other = make_client("someone-else@example.com")
    assert other.get(f"/companies/{company['id']}/employees").status_code == 404
    assert other.delete(f"/companies/{company['id']}/employees/{employee['id']}").status_code == 404
