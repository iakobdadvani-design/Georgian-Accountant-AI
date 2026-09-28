"""How to pay a tax: what to type into a payment order in the taxpayer's own bank. The app never moves money.

Every tax is paid to one treasury code; the Revenue Service assigns the money to what the taxpayer owes
(single treasury code since 2016). Bank links open each bank's own internet banking, where the customer
signs in themselves.
"""

import re

from pydantic import BaseModel, HttpUrl

TREASURY_BANK_CODE = "TRESGE22"
TREASURY_CODE = "101001000"
SOURCES = [
    "https://treasury.ge/en/page/banking-settlements-of-accounts",
    "https://treasury.ge/ka/page/TreasuryCodes",
]


class Bank(BaseModel):
    id: str  # the page shows `bank.<id>` from its catalog
    url: HttpUrl
    color: str


BANKS = [
    Bank(id="tbc", url="https://tbconline.ge/tbcrd/", color="#00A3E0"),
    Bank(id="bog", url="https://bonline.bog.ge/", color="#FF6000"),
    Bank(id="liberty", url="https://www.libertybank.ge/", color="#D2232A"),
    Bank(id="basis", url="https://bb.ge/", color="#1B3F8B"),
    Bank(id="procredit", url="https://www.procreditbank.ge/", color="#D8232A"),
    Bank(id="credo", url="https://credobank.ge/", color="#00843D"),
    Bank(id="tera", url="https://terabank.ge/", color="#5B2C83"),
    Bank(id="halyk", url="https://halykbank.ge/", color="#00805F"),
]

# Deadline -> the books summary field whose rule result is the amount due for that deadline's month.
AMOUNT_FROM_BOOKS = {
    "ge.vat.monthly_return": "vat_payable",
    "ge.small_business.monthly_return": "small_business_tax",
}


class PaymentDetails(BaseModel):
    treasury_code: str = TREASURY_CODE
    bank_code: str = TREASURY_BANK_CODE
    banks: list[Bank] = BANKS
    sources: list[str] = SOURCES


GEORGIAN_IBAN = re.compile(r"^GE\d{2}[A-Z]{2}\d{16}$")


def normalize_iban(text: str) -> str | None:
    """A Georgian IBAN without spaces, upper-case, if its format and ISO 13616 check digits are right."""
    iban = re.sub(r"\s+", "", text).upper()
    if not GEORGIAN_IBAN.match(iban):
        return None
    digits = "".join(str(int(c, 36)) for c in iban[4:] + iban[:4])
    return iban if int(digits) % 97 == 1 else None
