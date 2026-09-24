from decimal import Decimal

COMPANY = {"name": "Test LLC", "tax_id": "404000001", "legal_form": "LLC", "registration_date": "2024-01-15"}


def create_company(client, **overrides):
    response = client.post("/companies", json={**COMPANY, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def create_employee(client, company_id, **overrides):
    payload = {
        "full_name": "Nino Beridze",
        "personal_id": "01001012345",
        "gross_monthly_salary": "2500.50",
        "hired_on": "2024-02-01",
        **overrides,
    }
    return client.post(f"/companies/{company_id}/employees", json=payload)


def test_create_and_list_companies(client):
    company = create_company(client)
    assert client.get(f"/companies/{company['id']}").json()["name"] == "Test LLC"
    assert [c["id"] for c in client.get("/companies").json()] == [company["id"]]


def test_duplicate_tax_id_rejected(client):
    create_company(client)
    assert client.post("/companies", json=COMPANY).status_code == 409


def test_unknown_company_returns_404(client):
    assert client.get("/companies/00000000-0000-0000-0000-000000000000/employees").status_code == 404


def test_tax_profile_upsert(client):
    company = create_company(client)
    url = f"/companies/{company['id']}/tax-profile"
    assert client.get(url).status_code == 404

    assert client.put(url, json={"vat_registered": True, "vat_registration_date": "2024-03-01"}).status_code == 200
    response = client.put(url, json={"tax_regime": "small_business"})
    assert response.status_code == 200
    assert response.json()["tax_regime"] == "small_business"
    assert response.json()["vat_registered"] is False


def test_employee_salary_kept_exact(client):
    company = create_company(client)
    assert create_employee(client, company["id"]).status_code == 201
    assert create_employee(client, company["id"]).status_code == 409

    [employee] = client.get(f"/companies/{company['id']}/employees").json()
    assert Decimal(employee["gross_monthly_salary"]) == Decimal("2500.50")
    assert employee["currency"] == "GEL"


def test_transaction_rejects_other_companys_employee(client):
    a = create_company(client)
    b = create_company(client, tax_id="404000002")
    employee = create_employee(client, b["id"]).json()

    txn = {"occurred_on": "2024-05-01", "direction": "expense", "amount": "1000", "category": "salary",
           "employee_id": employee["id"]}
    assert client.post(f"/companies/{a['id']}/transactions", json=txn).status_code == 422
    assert client.post(f"/companies/{b['id']}/transactions", json=txn).status_code == 201


def test_transaction_amount_must_be_positive(client):
    company = create_company(client)
    txn = {"occurred_on": "2024-05-01", "direction": "income", "amount": "-5", "category": "sales"}
    assert client.post(f"/companies/{company['id']}/transactions", json=txn).status_code == 422


def test_tax_events_sorted_by_due_date(client):
    company = create_company(client)
    url = f"/companies/{company['id']}/tax-events"
    for due in ["2024-07-15", "2024-06-15"]:
        response = client.post(url, json={"tax_type": "vat", "period_start": "2024-05-01",
                                          "period_end": "2024-05-31", "due_date": due})
        assert response.status_code == 201
    events = client.get(url).json()
    assert [e["due_date"] for e in events] == ["2024-06-15", "2024-07-15"]
    assert events[0]["status"] == "pending"


def test_tax_event_period_validation(client):
    company = create_company(client)
    response = client.post(f"/companies/{company['id']}/tax-events", json={
        "tax_type": "vat", "period_start": "2024-06-01", "period_end": "2024-05-01", "due_date": "2024-07-15",
    })
    assert response.status_code == 422
