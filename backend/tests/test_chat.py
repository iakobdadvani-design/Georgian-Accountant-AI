from decimal import Decimal

import pytest

from app.chat.extractor import KeywordExtractor, parse_amount


@pytest.mark.parametrize("text, expected", [
    ("GEL 2,500", "2500"),
    ("2 500 lari", "2500"),
    ("salary 2500.50", "2500.50"),
    ("1,234,567.89 revenue", "1234567.89"),
    ("no number here", None),
    ("turnover for the last 12 months is 150,000", "150000"),
])
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("message, intent", [
    ("I hired someone for GEL 2,500", "calculate_payroll_tax"),
    ("ხელფასი 2500 ლარი", "calculate_payroll_tax"),
    ("Our annual revenue is 150,000", "check_vat_registration"),
    ("წლიური შემოსავალი 150000", "check_vat_registration"),
    ("Do I need to register for VAT?", "check_vat_registration"),
    ("I run a private clinic", "unknown"),  # "private" must not match "vat"
    ("hello", "unknown"),
])
def test_keyword_intents(message, intent):
    assert KeywordExtractor().extract(message).intent == intent


@pytest.fixture
def company(client):
    company = client.post("/companies", json={
        "name": "Chat LLC", "tax_id": "404222222", "legal_form": "LLC", "registration_date": "2024-01-01",
    }).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": False})
    return company


def chat(client, company, message, as_of="2025-06-01"):
    response = client.post(f"/companies/{company['id']}/chat", json={"message": message, "as_of": as_of})
    assert response.status_code == 200, response.text
    return response.json()


def test_payroll_message_runs_only_payroll_rules(client, company):
    body = chat(client, company, "I hired someone for GEL 2,500")
    assert body["extraction"]["entities"] == {"gross_salary": "2500", "pension_participant": True}
    assert body["extraction"]["assumed"] == ["pension_participant"]
    [result] = body["results"]
    assert result["rule_id"] == "ge.payroll.income_tax"
    assert Decimal(result["amount"]) == Decimal("490.00")
    assert {line["name"]: line["amount"] for line in result["breakdown"]} == {
        "employee_pension": "50.00", "income_tax": "490.00", "net_salary": "1960.00",
        "employer_pension": "50.00", "employer_cost": "2550.00"}
    assert body["reply"].startswith("For a gross salary of 2 500 GEL, the employee takes home 1 960.00 GEL.")
    assert "costs you 2 550.00 GEL in total" in body["reply"]
    assert "I've assumed the employee is in the funded pension scheme" in body["reply"]


def test_no_rule_before_effective_date(client, company):
    body = chat(client, company, "salary 2500", as_of="2018-06-01")
    assert body["results"] == []
    assert body["reply"] == "I don't have a rule in effect for that on the selected date."


def test_missing_amount_asks_for_it(client, company):
    body = chat(client, company, "I want to hire an employee")
    assert body["results"][0]["status"] == "insufficient_data"
    assert "What is the gross monthly salary?" in body["reply"]
    assert body["questions"] == ["What is the gross monthly salary?"]


def test_vat_message_uses_real_rule(client, company):
    body = chat(client, company, "Our turnover for the last 12 months is 150,000")
    [result] = body["results"]
    assert result["rule_id"] == "ge.vat.registration_threshold"
    assert result["status"] == "applies"
    assert result["verification"] == "unverified"
    assert body["reply"].startswith("Yes, you need to register for VAT.")
    assert "hasn't been reviewed by an accountant" in body["reply"]
    assert body["reply_source"] == "template"


@pytest.mark.parametrize("message, starts, has_suggestions", [
    ("გამარჯობა", "გამარჯობა!", True),
    ("გამარჯობათ!", "გამარჯობა!", True),
    ("hello", "Hi!", True),
    ("მადლობა", "არაფრის!", False),
    ("thanks a lot", "You're welcome!", False),
    ("What's the weather in Batumi?", "I can't answer that one yet.", True),
    ("ამინდი როგორია?", "ამ კითხვაზე პასუხი ჯერ არ შემიძლია.", True),
])
def test_off_topic_replies_match_language(client, company, message, starts, has_suggestions):
    body = chat(client, company, message)
    assert body["results"] == []
    assert body["reply"].startswith(starts)
    assert bool(body["suggestions"]) is has_suggestions
    if body["suggestions"]:
        georgian = any("Ⴀ" <= ch <= "ჿ" for ch in message)
        assert all(any("Ⴀ" <= ch <= "ჿ" for ch in s) == georgian for s in body["suggestions"])


def test_hire_is_not_a_greeting(client, company):
    assert chat(client, company, "hire someone for 2000")["extraction"]["intent"] == "calculate_payroll_tax"


def test_suggestions_are_understood(client, company):
    from app.chat.responder import SUGGESTIONS
    for language, examples in SUGGESTIONS.items():
        for example in examples:
            assert chat(client, company, example)["extraction"]["intent"] != "unknown", (language, example)


def test_greeting_keeps_pending_question(client, company):
    first = chat(client, company, "I want to hire an employee")
    cid = first["conversation_id"]
    body = {"message": "hi", "as_of": "2025-06-01", "conversation_id": cid}
    assert client.post(f"/companies/{company['id']}/chat", json=body).status_code == 200
    body["message"] = "2500"
    follow_up = client.post(f"/companies/{company['id']}/chat", json=body).json()
    assert follow_up["used_context"] is True
    assert follow_up["results"][0]["amount"] == "490.00"


def test_chat_page_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Georgian AI Accountant" in response.text


def test_chat_status_reports_offline_mode(client):
    assert client.get("/chat/status").json() == {"ai_enabled": False, "provider": None, "model": None,
                                                  "replies": "template", "legal_index": False}


# --- answers read like an accountant, not a report ---

@pytest.fixture
def registered(client):
    company = client.post("/companies", json={
        "name": "Registered LLC", "tax_id": "404888888", "legal_form": "LLC", "registration_date": "2024-01-01",
    }).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": True})
    return company


@pytest.mark.parametrize("message, expected", [
    ("უნდა დავრეგისტრირდე დღგ-ის გადამხდელად?",
     "არა, რეგისტრაცია არ გჭირდებათ. კომპანია უკვე რეგისტრირებულია დღგ-ის გადამხდელად"),
    ("Do I need to register for VAT?",
     "No, you don't need to register. The company is already registered as a VAT payer"),
])
def test_already_registered_gets_a_real_answer(client, registered, message, expected):
    body = chat(client, registered, message)
    assert body["reply"].startswith(expected)
    [result] = body["results"]
    assert result["status"] == "not_applicable"
    assert result["reasons"]  # the engine says *why*, from the rule file


def test_vat_question_without_turnover_explains_and_asks(client, company):
    body = chat(client, company, "უნდა დავრეგისტრირდე დღგ-ის გადამხდელად?")
    assert body["reply"].startswith("ეს დამოკიდებულია თქვენს ბრუნვაზე.")
    assert body["reply"].count("რამდენი იყო დღგ-ით დასაბეგრი") == 1  # asked once, not repeated as a list
    assert body["questions"] == ["რამდენი იყო დღგ-ით დასაბეგრი ოპერაციების ჯამი ბოლო 12 თვის განმავლობაში?"]


def test_below_threshold_says_no_and_why(client, company):
    body = chat(client, company, "ბოლო 12 თვის ბრუნვა 90 000 ლარია")
    assert body["reply"].startswith("არა, რეგისტრაცია არ გჭირდებათ. ბოლო 12 თვის დასაბეგრი ოპერაციების ჯამი არ აღემატება")


def test_georgian_payroll_answer(client, company):
    body = chat(client, company, "ხელფასი 1800 ლარი")
    assert body["reply"].startswith("1 800 ლარიანი ხელფასიდან თანამშრომელს ხელზე დარჩება 1 411.20 ლარი.")
    assert "ვივარაუდე, რომ თანამშრომელი დაგროვებით საპენსიო სქემაშია ჩართული" in body["reply"]


def test_bare_number_follow_up_keeps_georgian(client, company):
    first = chat(client, company, "უნდა დავრეგისტრირდე დღგ-ის გადამხდელად?")
    follow_up = client.post(f"/companies/{company['id']}/chat", json={
        "message": "150 000", "as_of": "2025-06-01", "conversation_id": first["conversation_id"]}).json()
    assert follow_up["extraction"]["language"] == "ka"
    assert follow_up["reply"].startswith("დიახ, დღგ-ის გადამხდელად რეგისტრაცია გჭირდებათ.")


def test_not_in_pension_scheme_stated_up_front(client, company):
    body = chat(client, company, "salary 2500, not in the pension scheme")
    assert body["extraction"]["assumed"] == []
    assert body["reply"].startswith("For a gross salary of 2 500 GEL, the employee takes home 2 000.00 GEL")
    assert "I've assumed" not in body["reply"]


def test_pension_correction_recomputes_previous_salary(client, company):
    first = chat(client, company, "ხელფასი 2500")
    body = {"message": "საპენსიოში არ არის", "as_of": "2025-06-01", "conversation_id": first["conversation_id"]}
    corrected = client.post(f"/companies/{company['id']}/chat", json=body).json()
    assert corrected["used_context"] is True
    assert corrected["extraction"]["entities"] == {"gross_salary": "2500", "pension_participant": False}
    assert corrected["reply"].startswith("2 500 ლარიანი ხელფასიდან თანამშრომელს ხელზე დარჩება 2 000.00 ლარი")


def test_new_salary_on_same_topic_is_a_new_question(client, company):
    first = chat(client, company, "salary 2500, not in the pension scheme")
    body = {"message": "and for salary 3000?", "as_of": "2025-06-01", "conversation_id": first["conversation_id"]}
    second = client.post(f"/companies/{company['id']}/chat", json=body).json()
    # a new figure doesn't silently inherit the earlier "no pension" answer; the default is restated
    assert second["extraction"]["entities"]["gross_salary"] == "3000"
    assert second["extraction"]["assumed"] == ["pension_participant"]


# --- VAT on a sale, profit distribution ---

@pytest.mark.parametrize("message, start", [
    ("How much VAT is in 11,800 GEL including VAT?",
     "11 800.00 GEL including VAT contains 1 800.00 GEL of VAT, so the price without VAT is 10 000.00 GEL."),
    ("I sold goods for 10,000 plus VAT", "VAT at 18% on 10 000.00 GEL is 1 800.00 GEL, so the total with VAT is 11 800.00 GEL."),
    ("ინვოისი 1180 ლარი დღგ-ს ჩათვლით", "1 180.00 ლარი დღგ-ს ჩათვლით შეიცავს 180.00 ლარის დღგ-ს"),
])
def test_vat_on_a_sale(client, registered, message, start):
    assert chat(client, registered, message)["reply"].startswith(start)


def test_vat_on_a_sale_when_not_registered(client, company):
    body = chat(client, company, "invoice for 5000 plus VAT")
    assert body["reply"].startswith("There's no VAT to add. The company isn't registered as a VAT payer")


@pytest.mark.parametrize("answer, expected", [
    ("yes", "5 000.00 GEL including VAT contains 762.71 GEL of VAT"),
    ("no", "VAT at 18% on 5 000.00 GEL is 900.00 GEL"),
    ("კი", "5 000.00 ლარი დღგ-ს ჩათვლით შეიცავს 762.71 ლარის დღგ-ს"),
])
def test_vat_asks_whether_price_includes_vat_and_accepts_yes_no(client, registered, answer, expected):
    message = "ინვოისი 5000 ლარი" if answer == "კი" else "invoice for 5000"
    first = chat(client, registered, message)
    assert "include" in first["reply"] or "შეიცავს" in first["reply"]
    body = {"message": answer, "as_of": "2025-06-01", "conversation_id": first["conversation_id"]}
    follow_up = client.post(f"/companies/{registered['id']}/chat", json=body).json()
    assert follow_up["used_context"] is True
    assert follow_up["reply"].startswith(expected)


def test_dividend_distribution(client, company):
    body = chat(client, company, "We want to pay 8,500 GEL in dividends")
    assert body["reply"].startswith(
        "If the company pays out 8 500 GEL in dividends, it owes 1 500.00 GEL profit tax")
    assert "costs the company 10 000.00 GEL in total" in body["reply"]
    assert "you withhold 425.00 GEL dividend tax (5%), so the owner receives 8 075.00 GEL" in body["reply"]
    assert "I've assumed the dividend goes to an individual owner" in body["reply"]
    assert {r["rule_id"] for r in body["results"]} == {"ge.profit.distribution", "ge.dividend.withholding"}


def test_dividend_to_a_company_is_not_withheld(client, company):
    body = chat(client, company, "dividend of 8500 to our parent company")
    assert "1 500.00 GEL profit tax" in body["reply"]
    assert "Dividends paid to another company are not taxed at source" in body["reply"]


def test_profit_tax_question_without_amount_explains_the_model(client, company):
    body = chat(client, company, "მოგების გადასახადი რამდენია?")
    assert body["reply"].startswith("საქართველოში კომპანია მოგების გადასახადს იხდის მხოლოდ მოგების განაწილებისას")


def test_individual_entrepreneur_has_no_distribution_profit_tax(client):
    ie = client.post("/companies", json={
        "name": "Nino IE", "tax_id": "01001099999", "legal_form": "IE", "registration_date": "2024-01-01"}).json()
    body = chat(client, ie, "dividend 5000")
    assert body["reply"].startswith("This calculation covers companies (LLC, JSC).")


def test_intent_specific_question_is_asked_once(client, registered):
    reply = chat(client, registered, "ინვოისი 5000 ლარი")["reply"]
    assert reply == "რა თქმა უნდა. 5 000 ლარი უკვე შეიცავს დღგ-ს, თუ დღგ ზემოდან ემატება?"
