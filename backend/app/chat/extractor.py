"""Message -> structured intent + entities. The AI layer's only job on the way in; it never computes tax."""

import re
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel

Intent = Literal[
    "calculate_payroll_tax", "check_vat_registration", "calculate_vat", "calculate_distribution", "list_deadlines",
    "unknown",
]
Language = Literal["en", "ka"]

# Which input fact each intent's amount becomes; the rules engine decides which rules read that fact.
INTENT_AMOUNT_FACT: dict[str, str] = {
    "calculate_payroll_tax": "gross_salary",
    "check_vat_registration": "taxable_turnover_12m",
    "calculate_vat": "sale_amount",
    "calculate_distribution": "distribution_amount",
}


class Extraction(BaseModel):
    intent: Intent
    entities: dict[str, str | bool] = {}
    # Entities filled with a default rather than stated by the user; the reply says so.
    assumed: list[str] = []
    language: Language = "en"
    source: Literal["keyword", "claude", "ollama"] = "keyword"
    matched_keywords: list[str] = []


class Extractor(Protocol):
    def extract(self, message: str) -> Extraction: ...


# Checked in order; the first group with a hit wins. Registration words beat VAT-amount words
# ("register for VAT"), and the bare "vat"/"დღგ" only means registration when nothing more specific matched.
KEYWORDS: list[tuple[Intent, list[str]]] = [
    ("list_deadlines", ["deadline", "due", "calendar", "what do i need to file", "ვადა", "ვადებ", "ვადის",
                        "კალენდარ", "დეკლარაცი", "რა უნდა ჩავაბარო", "როდის უნდა გადავიხადო"]),
    ("calculate_distribution", ["dividend", "distribut", "pay out profit", "profit tax", "დივიდენდ", "განაწილ",
                                "მოგების გადასახად"]),
    ("calculate_payroll_tax", ["salary", "payroll", "wage", "hired", "hire", "employee", "pension", "ხელფას",
                               "დავიქირავე", "თანამშრომ", "საპენსიო", "პენსი"]),
    ("check_vat_registration", ["regist", "turnover", "revenue", "რეგისტრ", "ბრუნვ", "შემოსავ"]),
    ("calculate_vat", ["invoice", "how much vat", "vat on", "vat for", "vat in", "vat amount", "price", "sold",
                       "sell", "including vat", "incl", "excluding vat", "excl", "plus vat", "ინვოის", "ანგარიშ-ფაქტ",
                       "ფასი", "გავყიდე", "ვყიდი", "რამდენი დღგ", "დღგ რამდენ", "ჩათვლით", "გარეშე"]),
    ("check_vat_registration", ["vat", "sales", "დღგ"]),
]

# "not in the pension scheme", "opted out of pension", "საპენსიოში არ არის", "არ არის საპენსიო სქემაში"
NO_PENSION = re.compile(
    r"\b(not|isn't|isnt|no longer|opted out|opt(ed)? out|without|no)\b[^.?!]{0,30}\bpension"
    r"|\bpension\b[^.?!]{0,20}\b(opted out|exempt)"
    r"|\bარ\b[^.?!]{0,25}(საპენსიო|პენსი)|(საპენსიო|პენსი)[^.?!]{0,25}\bარ\b",
    re.I,
)


NOT_INCLUDED = re.compile(
    r"\b(excl|excluding|without|before|plus|net of|not includ|doesn'?t include|does not include)\b[^.?!]{0,15}\bvat\b"
    r"|\+\s*vat|\bnet\b|\bvat\b[^.?!]{0,15}\b(on top|extra|excluded|not included)"
    r"|დღგ-?(ის|ს)?\s*(გარეშე|გარდა)|\+\s*დღგ|პლუს\s+დღგ|დღგ-ს\s+არ\s+შეიცავს",
    re.I,
)
INCLUDED = re.compile(
    r"\b(incl|including|includes|included|inclusive|with)\b[^.?!]{0,15}\bvat\b|\bvat\b[^.?!]{0,10}\b(included|inclusive)"
    r"|\bgross\b|დღგ-?(ის|ს)?\s*ჩათვლით|დღგ-ით|დღგ-ს\s+შეიცავს",
    re.I,
)
YES = re.compile(r"^\W*(yes|yeah|yep|yup|correct|right|it does|sure|კი|დიახ|ჰო|ხო|კაი)\b", re.I)
NO = re.compile(r"^\W*(no|nope|not|it doesn'?t|არა|არ)\b", re.I)
TO_COMPANY = re.compile(r"\b(to|for) (a|an|another|our|the|my)? ?(company|llc|parent|holding|enterprise)\b"
                        r"|კომპანიას|საწარმოს|შპს-ს|ჰოლდინგ", re.I)


def vat_inclusive_flag(message: str) -> bool | None:
    """Whether a stated price already includes VAT; None if the message doesn't say."""
    if NOT_INCLUDED.search(message):
        return False
    if INCLUDED.search(message):
        return True
    return None


def yes_no(message: str) -> bool | None:
    if YES.search(message):
        return True
    if NO.search(message):
        return False
    return None


def dividend_recipient(message: str) -> str | None:
    return "company" if TO_COMPANY.search(message) else None


def pension_flag(message: str) -> bool | None:
    """False when the user says the employee isn't in the funded pension scheme; otherwise unknown."""
    return False if NO_PENSION.search(message) else None


GEORGIAN = re.compile(r"[Ⴀ-ჿ]")

# 2500 | 2,500 | 2 500 | 2500.50 | 1,234,567.89
AMOUNT = re.compile(r"(?<![\d.])(\d{1,3}(?:[ ,]\d{3})+|\d+)(?:\.(\d{1,2}))?(?![\d])")


def detect_language(message: str) -> Language:
    return "ka" if GEORGIAN.search(message) else "en"


def normalize_amount(raw: str) -> str | None:
    """'2,500' / '2 500' / '2500.50' -> exact decimal string; None if it isn't a plain non-negative amount."""
    match = AMOUNT.fullmatch(raw.strip())
    if match is None:
        return None
    whole = re.sub(r"[ ,]", "", match.group(1))
    return str(Decimal(f"{whole}.{match.group(2)}" if match.group(2) else whole))


def parse_amount(message: str) -> str | None:
    """Largest amount in the message as an exact decimal string, or None.

    Largest, not first: in "turnover for the last 12 months is 150,000" the 12 is a period, not the amount.
    """
    amounts = [normalize_amount(m.group(0)) for m in AMOUNT.finditer(message)]
    return max((a for a in amounts if a is not None), key=Decimal, default=None)


class KeywordExtractor:
    """Offline fallback: first intent whose keyword appears wins."""

    def extract(self, message: str) -> Extraction:
        text = message.lower()
        language = detect_language(message)
        for intent, words in KEYWORDS:
            hits = [w for w in words if re.search(r"\b" + re.escape(w), text)]  # word-prefix: "vat" not "private"
            if hits:
                entities: dict[str, str | bool] = {}
                amount = parse_amount(message)
                if amount is not None and intent in INTENT_AMOUNT_FACT:
                    entities[INTENT_AMOUNT_FACT[intent]] = amount
                if intent == "calculate_payroll_tax" and pension_flag(message) is False:
                    entities["pension_participant"] = False
                if intent == "calculate_vat" and (inclusive := vat_inclusive_flag(message)) is not None:
                    entities["vat_inclusive"] = inclusive
                if intent == "calculate_distribution" and (recipient := dividend_recipient(message)):
                    entities["dividend_recipient"] = recipient
                return Extraction(intent=intent, entities=entities, language=language, matched_keywords=hits)
        return Extraction(intent="unknown", language=language)
