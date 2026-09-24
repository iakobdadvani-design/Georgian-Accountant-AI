"""RS.ge taxpayer lookup: SOAP client against a mocked transport, and the /rs endpoints with a fake client."""

import re

import httpx
import pytest

from app.api.rsge import get_rs_client
from app.main import app
from app.rsge import RSAuthError, RSClient, RSError, Taxpayer

URL = "https://services.rs.ge/WayBillService/WayBillService.asmx"


def soap(operation: str, inner: str) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/xml; charset=utf-8"}, content=(
        '<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        f'<soap:Body><{operation}Response xmlns="http://tempuri.org/">{inner}</{operation}Response></soap:Body></soap:Envelope>'
    ).encode())


def rs_returning(user_ok=True, name="შპს თბილისი", vat="true", seen=None) -> RSClient:
    def handler(request: httpx.Request) -> httpx.Response:
        operation = request.headers["SOAPAction"].strip('"').rsplit("/", 1)[1]
        if seen is not None:
            seen.append((operation, request.content.decode()))
        if operation == "chek_service_user":
            return soap(operation, f"<chek_service_userResult>{str(user_ok).lower()}</chek_service_userResult>"
                                   "<un_id>1</un_id><s_user_id>2</s_user_id>")
        if operation == "get_name_from_tin":
            return soap(operation, f"<get_name_from_tinResult>{name}</get_name_from_tinResult>")
        return soap(operation, f"<is_vat_payer_tinResult>{vat}</is_vat_payer_tinResult>")

    return RSClient(URL, "user:1", "p<&>", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_lookup_returns_name_and_vat_status():
    seen = []
    assert rs_returning(seen=seen).lookup("404123456") == Taxpayer("404123456", "შპს თბილისი", True)
    assert [op for op, _ in seen] == ["chek_service_user", "get_name_from_tin", "is_vat_payer_tin"]
    body = seen[1][1]
    assert "<su>user:1</su>" in body and "<sp>p&lt;&amp;&gt;</sp>" in body and "<tin>404123456</tin>" in body


def test_lookup_not_vat_payer():
    assert rs_returning(vat="false").lookup("404123456").vat_payer is False


def test_unknown_code_is_none():
    assert rs_returning(name="").lookup("000000000") is None


def test_rejected_service_user():
    with pytest.raises(RSAuthError):
        rs_returning(user_ok=False).lookup("404123456")


def test_unexpected_vat_answer_is_an_error():
    with pytest.raises(RSError):
        rs_returning(vat="").lookup("404123456")


@pytest.mark.parametrize("handler", [
    lambda r: httpx.Response(500, content=b"<soap:Fault/>"),
    lambda r: httpx.Response(200, content=b"not xml"),
    lambda r: (_ for _ in ()).throw(httpx.ConnectTimeout("slow")),
])
def test_transport_failures_are_rs_errors(handler):
    rs = RSClient(URL, "u", "p", client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(RSError):
        rs.lookup("404123456")


class FakeRS:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def lookup(self, tin):
        self.calls.append(tin)
        if self.error:
            raise self.error
        return self.result


def use(rs):
    app.dependency_overrides[get_rs_client] = lambda: rs


def test_endpoint_requires_sign_in(make_client):
    assert make_client().get("/rs/taxpayers/404123456").status_code == 401


def test_status_and_lookup_when_not_configured(client):
    assert client.get("/rs/status").json() == {"configured": False}
    response = client.get("/rs/taxpayers/404123456")
    assert response.status_code == 503 and response.json()["detail"] == "RS.ge lookup is not set up"


def test_lookup_found(client):
    rs = FakeRS(Taxpayer("404123456", "შპს თბილისი", True))
    use(rs)
    assert client.get("/rs/status").json() == {"configured": True}
    data = client.get("/rs/taxpayers/404123456").json()
    assert (data["tin"], data["name"], data["vat_payer"], data["source"]) == ("404123456", "შპს თბილისი", True, "rs.ge")
    assert re.match(r"\d{4}-\d{2}-\d{2}T", data["checked_at"])
    assert rs.calls == ["404123456"]


@pytest.mark.parametrize("tin", ["12345", "40412345a", "4041234567"])
def test_invalid_code_never_reaches_rs(client, tin):
    rs = FakeRS()
    use(rs)
    response = client.get(f"/rs/taxpayers/{tin}")
    assert response.status_code == 422 and response.json()["detail"] == "Enter a 9- or 11-digit code"
    assert rs.calls == []


@pytest.mark.parametrize("rs, code, detail", [
    (FakeRS(None), 404, "No taxpayer with this code on RS.ge"),
    (FakeRS(error=RSAuthError("no")), 502, "RS.ge rejected the service user"),
    (FakeRS(error=RSError("down")), 503, "RS.ge is not responding"),
])
def test_lookup_failures(client, rs, code, detail):
    use(rs)
    response = client.get("/rs/taxpayers/01001012345")
    assert response.status_code == code and response.json()["detail"] == detail
