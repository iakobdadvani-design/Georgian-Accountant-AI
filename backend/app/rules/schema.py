from datetime import date
from decimal import Decimal
from typing import Literal, Union

from pydantic import BaseModel, Field

FactValue = bool | int | float | str

# Plain text, or per-language text like {"en": "...", "ka": "..."}.
LocalizedText = str | dict[str, str]


def localize(text: LocalizedText | None, language: str) -> str | None:
    if text is None or isinstance(text, str):
        return text
    return text.get(language) or text.get("en") or next(iter(text.values()), None)


class Compare(BaseModel):
    fact: str
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte"]
    value: FactValue
    # Shown to the user when this condition is why the rule does not apply.
    if_false: LocalizedText | None = None


class AllOf(BaseModel):
    all: list["Condition"] = Field(min_length=1)


class AnyOf(BaseModel):
    any: list["Condition"] = Field(min_length=1)


Condition = Union[Compare, AllOf, AnyOf]


class Percentage(BaseModel):
    type: Literal["percentage"]
    base: str
    rate: Decimal


class Fixed(BaseModel):
    type: Literal["fixed"]
    amount: Decimal


Calculation = Union[Percentage, Fixed]


class LegalSource(BaseModel):
    citation: LocalizedText
    url: str | None = None
    note: str | None = None
    # How to find the supporting passage in the legal index (all words must match).
    search_query: str | None = None
    document_id: str | None = None
    language: str | None = None


class Passage(BaseModel):
    """A retrieved excerpt of legal text. Shown as evidence; never used to compute anything."""

    chunk_id: int
    title: str
    url: str
    publication: str
    language: str
    excerpt: str


Verification = Literal["demo", "unverified", "verified"]


class TaxRule(BaseModel):
    """One version of a rule. A rule_id may have several versions with non-overlapping effective ranges."""

    rule_id: str
    version: int = Field(ge=1)
    title: LocalizedText
    tax_type: str
    effective_from: date
    effective_to: date | None = None
    conditions: Condition
    calculation: Calculation | None = Field(default=None, discriminator="type")
    message: LocalizedText | None = None
    legal_source: LegalSource
    last_verified_date: date | None = None
    is_demo: bool = False

    def is_effective_on(self, day: date) -> bool:
        return self.effective_from <= day and (self.effective_to is None or day <= self.effective_to)

    @property
    def verification(self) -> Verification:
        if self.is_demo:
            return "demo"
        return "verified" if self.last_verified_date else "unverified"


class RuleResult(BaseModel):
    rule_id: str
    version: int
    title: LocalizedText
    tax_type: str
    status: Literal["applies", "not_applicable", "insufficient_data"]
    amount: Decimal | None = None
    message: LocalizedText | None = None
    reasons: list[LocalizedText] = Field(default=[], description="Why the rule does not apply (failed conditions)")
    missing_facts: list[str] = []
    trace: list[str] = []
    legal_source: LegalSource
    is_demo: bool
    verification: Verification
    last_verified_date: date | None = None
    citations: list[Passage] = []
