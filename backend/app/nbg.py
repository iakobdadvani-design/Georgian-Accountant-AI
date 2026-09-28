"""Official lari exchange rates from the National Bank of Georgia (nbg.gov.ge public API).

Tax Code Art. 73(10): a transaction in a foreign currency is translated into lari (a) at the NBG official rate for
the transaction day or, (b) if there is none for that day, at the rate defined under the NBG Board's procedure.
For (b) we use the latest official rate published before that day and record which day it is from; an accountant
should confirm this reading of the Board's procedure.
"""

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import httpx

URL = "https://nbg.gov.ge/gw/api/ct/monetarypolicy/currencies/en/json"
TIMEOUT_SECONDS = 10.0
LOOKBACK_DAYS = 10  # how far back to look for the latest rate when the day itself has none


class NBGError(Exception):
    """The National Bank's service could not answer, or answered something unexpected."""


@dataclass(frozen=True)
class Rate:
    currency: str
    lari: Decimal   # lari for 1 unit of the currency
    day: date       # the day the rate is officially valid for


_shared: "NBGClient | None" = None


def get_nbg() -> "NBGClient":
    """One client (and rate cache) for the app; tests override this and never call the NBG."""
    global _shared
    if _shared is None:
        _shared = NBGClient()
    return _shared


class NBGClient:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)
        self.cache: dict[tuple[str, date], Rate | None] = {}

    def rate(self, currency: str, day: date) -> Rate:
        """The official rate for `day`, or the latest one before it (Art. 73(10)(b)); NBGError if none is found."""
        for back in range(LOOKBACK_DAYS + 1):
            found = self._on(currency, day - timedelta(days=back))
            if found is not None:
                return found
        raise NBGError(f"no official {currency} rate within {LOOKBACK_DAYS} days before {day}")

    def _on(self, currency: str, day: date) -> Rate | None:
        key = (currency, day)
        if key not in self.cache:
            self.cache[key] = self._fetch(currency, day)
        return self.cache[key]

    def _fetch(self, currency: str, day: date) -> Rate | None:
        try:
            response = self.client.get(URL, params={"currencies": currency, "date": day.isoformat()})
            response.raise_for_status()
            data = json.loads(response.content, parse_float=Decimal)
        except (httpx.HTTPError, ValueError) as e:
            raise NBGError(f"{currency} {day}: {e}") from e
        for block in data if isinstance(data, list) else []:
            for c in block.get("currencies", []):
                if c.get("code") == currency and c.get("rate") and c.get("quantity"):
                    valid = str(c.get("validFromDate") or block.get("date") or day.isoformat())[:10]
                    if date.fromisoformat(valid) != day:
                        return None  # a rate carried from another day is looked up for that day instead
                    return Rate(currency, Decimal(str(c["rate"])) / Decimal(str(c["quantity"])), day)
        return None
