"""A company's own RS.ge connection: checked against RS before it's stored, stored encrypted, never a real call."""

import pytest
from cryptography.fernet import Fernet

from app.api.rsge import get_rs_factory
from app.config import settings
from app.main import app
from app.models import CompanyRS
from app.rsge import RSAuthError, RSError, Taxpayer


class FakeRS:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.logins = result, error, []

    def factory(self, user, password):
        self.logins.append((user, password))
        return self

    def lookup(self, tin):
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(settings, "credentials_key", Fernet.generate_key().decode())


@pytest.fixture
def company(client):
    return client.post("/companies", json={"name": "RS LLC", "tax_id": "404777777", "legal_form": "LLC",
                                           "registration_date": "2024-01-01"}).json()


def use(rs):
    app.dependency_overrides[get_rs_factory] = lambda: rs.factory


LOGIN = {"service_user": "rs_llc_app", "password": "s3cret-pass"}


def test_not_connected_and_not_available_without_a_key(client, company, monkeypatch):
    monkeypatch.setattr(settings, "credentials_key", "")
    assert client.get(f"/companies/{company['id']}/rs").json() == {
        "available": False, "connected": False, "service_user": None, "status": None,
        "registered_name": None, "vat_payer": None, "checked_at": None}
    use(FakeRS(Taxpayer("404777777", "შპს „არეს“", True)))
    assert client.put(f"/companies/{company['id']}/rs", json=LOGIN).status_code == 503


def test_connect_checks_the_company_and_stores_the_password_encrypted(client, company, key, make_client):
    rs = FakeRS(Taxpayer("404777777", "შპს „არეს“", True))
    use(rs)
    connected = client.put(f"/companies/{company['id']}/rs", json=LOGIN).json()
    assert (connected["connected"], connected["status"], connected["registered_name"], connected["vat_payer"]) == (
        True, "ok", "შპს „არეს“", True)
    assert "password" not in str(connected) and rs.logins == [("rs_llc_app", "s3cret-pass")]

    from app.database import get_db
    db = next(app.dependency_overrides[get_db]())
    row = db.query(CompanyRS).one()
    assert row.password_encrypted != "s3cret-pass" and "s3cret" not in row.password_encrypted

    # re-check decrypts and logs in with the same details; RS now says not a VAT payer
    rs.result = Taxpayer("404777777", "შპს „არეს“", False)
    rechecked = client.post(f"/companies/{company['id']}/rs/check").json()
    assert (rechecked["status"], rechecked["vat_payer"]) == ("ok", False)
    assert rs.logins[-1] == ("rs_llc_app", "s3cret-pass")

    assert make_client("rs-intruder@example.com").get(f"/companies/{company['id']}/rs").status_code == 404
    assert client.delete(f"/companies/{company['id']}/rs").status_code == 204
    assert client.get(f"/companies/{company['id']}/rs").json()["connected"] is False
    assert client.delete(f"/companies/{company['id']}/rs").status_code == 404


@pytest.mark.parametrize("rs, code", [
    (FakeRS(error=RSAuthError("no")), 422),
    (FakeRS(error=RSError("down")), 503),
    (FakeRS(result=None), 404),  # RS doesn't know the company's tax ID
])
def test_failed_connections_store_nothing(client, company, key, rs, code):
    use(rs)
    assert client.put(f"/companies/{company['id']}/rs", json=LOGIN).status_code == code
    assert client.get(f"/companies/{company['id']}/rs").json()["connected"] is False


def test_recheck_records_a_rejected_service_user(client, company, key):
    rs = FakeRS(Taxpayer("404777777", "შპს „არეს“", True))
    use(rs)
    client.put(f"/companies/{company['id']}/rs", json=LOGIN)
    rs.error = RSAuthError("revoked")
    assert client.post(f"/companies/{company['id']}/rs/check").json()["status"] == "rejected"


def test_rename_company(client, company):
    renamed = client.patch(f"/companies/{company['id']}", json={"name": "  შპს „არეს“ "})
    assert renamed.status_code == 200 and renamed.json()["name"] == "შპს „არეს“"
    assert client.patch(f"/companies/{company['id']}", json={"name": ""}).status_code == 422
