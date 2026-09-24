import pytest

from app.auth import hash_password, verify_password
from tests.conftest import PASSWORD

COMPANY = {"name": "Mine LLC", "tax_id": "404555555", "legal_form": "LLC", "registration_date": "2024-01-01"}


def test_password_hashing():
    stored = hash_password("s3cret-pass")
    assert stored.startswith("scrypt$") and "s3cret-pass" not in stored
    assert verify_password("s3cret-pass", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("s3cret-pass", "garbage")
    assert hash_password("same") != hash_password("same")  # salted


# --- registration & login ---

def test_register_signs_in_and_hides_password(make_client):
    client = make_client()
    response = client.post("/auth/register", json={"email": " New@Example.COM ", "password": PASSWORD, "full_name": "N"})
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"
    assert "password" not in str(response.json())
    assert client.get("/auth/me").json()["email"] == "new@example.com"
    # the cookie must not be readable from page scripts
    assert "httponly" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize("body, code", [
    ({"email": "owner@example.com", "password": PASSWORD, "full_name": "Dup"}, 409),
    ({"email": "not-an-email", "password": PASSWORD, "full_name": "X"}, 422),
    ({"email": "short@example.com", "password": "short", "full_name": "X"}, 422),
])
def test_register_rejections(client, make_client, body, code):
    assert make_client().post("/auth/register", json=body).status_code == code


def test_login_logout(client, make_client):
    other = make_client()
    assert other.post("/auth/login", json={"email": "owner@example.com", "password": "nope"}).status_code == 401
    assert other.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}).status_code == 401
    assert other.post("/auth/login", json={"email": "OWNER@example.com", "password": PASSWORD}).status_code == 200
    assert other.get("/auth/me").status_code == 200

    assert other.post("/auth/logout").status_code == 204
    assert other.get("/auth/me").status_code == 401
    assert client.get("/auth/me").status_code == 200  # other sessions unaffected


def test_logged_out_token_cannot_be_replayed(make_client):
    client = make_client("replay@example.com")
    token = client.cookies.get("session")
    client.post("/auth/logout")
    attacker = make_client()
    attacker.cookies.set("session", token)
    assert attacker.get("/auth/me").status_code == 401


# --- data isolation ---

@pytest.mark.parametrize("path", ["/companies", "/conversations", "/auth/me"])
def test_protected_endpoints_need_login(make_client, path):
    assert make_client().get(path).status_code == 401


def test_users_cannot_see_each_others_companies(client, make_client):
    company = client.post("/companies", json=COMPANY).json()
    intruder = make_client("intruder@example.com")

    assert intruder.get("/companies").json() == []
    for path in ["", "/employees", "/tax-profile", "/transactions"]:
        assert intruder.get(f"/companies/{company['id']}{path}").status_code == 404
    assert intruder.post(f"/companies/{company['id']}/chat", json={"message": "salary 2500"}).status_code == 404
    # the same tax_id is allowed in a different account (e.g. owner and their accountant)
    assert intruder.post("/companies", json=COMPANY).status_code == 201


# --- conversations ---

@pytest.fixture
def company(client):
    company = client.post("/companies", json=COMPANY).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": False})
    return company


def chat(client, company, message, conversation_id=None):
    body = {"message": message, "as_of": "2025-06-01"}
    if conversation_id:
        body["conversation_id"] = conversation_id
    response = client.post(f"/companies/{company['id']}/chat", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_conversation_is_saved_with_results(client, company):
    first = chat(client, company, "I hired someone for GEL 2,500")
    cid = first["conversation_id"]
    chat(client, company, "Our turnover for the last 12 months is 150,000", cid)

    [summary] = client.get("/conversations", params={"company_id": company["id"]}).json()
    assert summary["id"] == cid
    assert summary["title"] == "I hired someone for GEL 2,500"

    detail = client.get(f"/conversations/{cid}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    saved = detail["messages"][1]["payload"]
    assert saved["results"][0]["rule_id"] == "demo.payroll_withholding"
    assert saved["results"][0]["amount"] == "300.00"
    assert saved["as_of"] == "2025-06-01"


def test_follow_up_answer_completes_pending_question(client, company):
    first = chat(client, company, "I want to hire an employee")
    assert first["questions"] == ["What is the gross monthly salary?"]

    follow_up = chat(client, company, "2500", first["conversation_id"])
    assert follow_up["used_context"] is True
    assert follow_up["extraction"]["intent"] == "calculate_payroll_tax"
    assert follow_up["results"][0]["amount"] == "300.00"
    assert follow_up["questions"] == []

    # once answered there is nothing pending: a bare number no longer means salary
    third = chat(client, company, "2500", first["conversation_id"])
    assert third["extraction"]["intent"] == "unknown"


def test_new_conversation_has_no_context(client, company):
    chat(client, company, "I want to hire an employee")
    fresh = chat(client, company, "2500")
    assert fresh["extraction"]["intent"] == "unknown"


def test_conversation_privacy_and_delete(client, company, make_client):
    cid = chat(client, company, "salary 2500")["conversation_id"]
    intruder = make_client("snoop@example.com")
    assert intruder.get(f"/conversations/{cid}").status_code == 404
    assert intruder.delete(f"/conversations/{cid}").status_code == 404

    assert client.delete(f"/conversations/{cid}").status_code == 204
    assert client.get(f"/conversations/{cid}").status_code == 404


def test_conversation_cannot_be_moved_to_another_company(client, company):
    cid = chat(client, company, "salary 2500")["conversation_id"]
    other = client.post("/companies", json={**COMPANY, "tax_id": "404666666"}).json()
    response = client.post(f"/companies/{other['id']}/chat", json={"message": "salary 1", "conversation_id": cid})
    assert response.status_code == 404
