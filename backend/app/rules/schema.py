import re
from datetime import date
from decimal import Decimal
from typing import Literal, Union

from pydantic import BaseModel, Field, model_validator

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


CONSTANT = re.compile(r"^-?\d+(\.\d+)?$")


class Step(BaseModel):
    """One named arithmetic step. Args are constants ("0.02"), fact names ("input.x") or earlier step names."""

    name: str = Field(pattern=r"^[a-z_][a-z0-9_]*$")
    label: LocalizedText
    op: Literal["multiply", "divide", "subtract", "add"]
    args: list[str] = Field(min_length=2)
    when: "Condition | None" = None  # if false, the step is 0 (e.g. not in the pension scheme)
    round: bool = True  # money steps round half-up to 0.01; intermediate bases may stay exact
    show: bool = True  # include in the result's breakdown


class Steps(BaseModel):
    type: Literal["steps"]
    steps: list[Step] = Field(min_length=1)
    result: str  # the step whose value is the result's `amount`

    @model_validator(mode="after")
    def check_references(self) -> "Steps":
        seen: set[str] = set()
        for step in self.steps:
            if step.name in seen:
                raise ValueError(f"duplicate step name {step.name!r}")
            for arg in step.args:
                # Facts are always dotted ("input.gross_salary"), so a bare unknown name is a typo.
                if not CONSTANT.match(arg) and "." not in arg and arg not in seen:
                    raise ValueError(f"step {step.name!r} uses {arg!r} before it is defined")
            seen.add(step.name)
        if self.result not in seen:
            raise ValueError(f"result {self.result!r} is not a step")
        return self


Calculation = Union[Percentage, Fixed, Steps]


class BreakdownLine(BaseModel):
    name: str
    label: LocalizedText
    amount: Decimal


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
    amount_label: LocalizedText | None = None  # what `amount` is, for step calculations
    breakdown: list[BreakdownLine] = []
    message: LocalizedText | None = None
    reasons: list[LocalizedText] = Field(default=[], description="Why the rule does not apply (failed conditions)")
    missing_facts: list[str] = []
    trace: list[str] = []
    legal_source: LegalSource
    is_demo: bool
    verification: Verification
    last_verified_date: date | None = None
    citations: list[Passage] = []


Step.model_rebuild()


class Monthly(BaseModel):
    """Due on `day` of the month after each monthly period."""

    type: Literal["monthly"]
    day: int = Field(ge=1, le=28)


class Annual(BaseModel):
    """Due each year on month/day; the period is the previous or the current calendar year."""

    type: Literal["annual"]
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=28)
    period: Literal["previous_year", "current_year"]


class Deadline(BaseModel):
    """A recurring filing or payment date, shown in the calendar when `applies` holds for the company."""

    deadline_id: str
    tax_type: str
    title: LocalizedText
    description: LocalizedText | None = None
    applies: Condition
    schedule: Monthly | Annual = Field(discriminator="type")
    legal_source: LegalSource
    last_verified_date: date | None = None

    @property
    def verification(self) -> Verification:
        return "verified" if self.last_verified_date else "unverified"
