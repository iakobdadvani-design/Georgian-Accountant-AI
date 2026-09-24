"""Taxpayer lookup through the Revenue Service's official web service (services.rs.ge, WayBillService).

Needs an RS "service user", created by the taxpayer in their own eservices.rs.ge account. Read-only:
the registered name and VAT-payer status for an identification code. Never the user's portal login.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from xml.sax.saxutils import escape

import httpx

NS = "http://tempuri.org/"
TIMEOUT_SECONDS = 15.0
# 9 digits for companies, 11 for individuals (personal number, e.g. an individual entrepreneur).
TIN_PATTERN = re.compile(r"^(\d{9}|\d{11})$")


class RSError(Exception):
    """RS.ge could not answer (network, SOAP fault, unexpected response)."""


class RSAuthError(RSError):
    """RS.ge rejected the service user."""


@dataclass(frozen=True)
class Taxpayer:
    tin: str
    name: str
    vat_payer: bool


class RSClient:
    def __init__(self, url: str, service_user: str, service_password: str, client: httpx.Client | None = None):
        self.url, self.su, self.sp = url, service_user, service_password
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)

    def lookup(self, tin: str) -> Taxpayer | None:
        """None when RS has no taxpayer with this code."""
        if self._call("chek_service_user").findtext(f"{{{NS}}}chek_service_userResult") != "true":
            raise RSAuthError("service user rejected")
        name = (self._call("get_name_from_tin", tin=tin).findtext(f"{{{NS}}}get_name_from_tinResult") or "").strip()
        if not name:
            return None
        vat = self._call("is_vat_payer_tin", tin=tin).findtext(f"{{{NS}}}is_vat_payer_tinResult")
        if vat not in ("true", "false"):
            raise RSError(f"unexpected VAT status {vat!r}")
        return Taxpayer(tin=tin, name=name, vat_payer=vat == "true")

    def _call(self, operation: str, **params: str) -> ET.Element:
        fields = {"su": self.su, "sp": self.sp, **params}
        body = "".join(f"<{k}>{escape(v)}</{k}>" for k, v in fields.items())
        envelope = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
            f'<{operation} xmlns="{NS}">{body}</{operation}></soap:Body></soap:Envelope>'
        )
        try:
            response = self.client.post(self.url, content=envelope.encode(), headers={
                "Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{NS}{operation}"',
            })
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except (httpx.HTTPError, ET.ParseError) as e:
            raise RSError(f"{operation}: {e}") from e
        result = root.find(f".//{{{NS}}}{operation}Response")
        if result is None:
            raise RSError(f"{operation}: no response element")
        return result
