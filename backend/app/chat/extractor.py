"""Message -> structured intent + entities. The AI layer's only job on the way in; it never computes tax."""

import re
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel

Intent = Literal["calculate_payroll_tax", "check_vat_registration", "unknown"]
Language = Literal["en", "ka"]

# Which input fact each intent's amount becomes; the rules engine decides which rules read that fact.
INTENT_AMOUNT_FACT: dict[str, str] = {
    "calculate_payroll_tax": "gross_salary",
    "check_vat_registration": "taxable_turnover_12m",
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


KEYWORDS: dict[str, list[str]] = {
    "calculate_payroll_tax": ["salary", "payroll", "wage", "hired", "hire", "employee", "pension", "ხელფას",
                              "დავიქირავე", "თანამშრომ", "საპენსიო", "პენსი"],
    "check_vat_registration": ["vat", "revenue", "turnover", "sales", "დღგ", "შემოსავ", "ბრუნვ"],
}

# "not in the pension scheme", "opted out of pension", "საპენსიოში არ არის", "არ არის საპენსიო სქემაში"
NO_PENSION = re.compile(
    r"\b(not|isn't|isnt|no longer|opted out|opt(ed)? out|without|no)\b[^.?!]{0,30}\bpension"
    r"|\bpension\b[^.?!]{0,20}\b(opted out|exempt)"
    r"|\bარ\b[^.?!]{0,25}(საპენსიო|პენსი)|(საპენსიო|პენსი)[^.?!]{0,25}\bარ\b",
    re.I,
)


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
        for intent, words in KEYWORDS.items():
            hits = [w for w in words if re.search(r"\b" + re.escape(w), text)]  # word-prefix: "vat" not "private"
            if hits:
                entities: dict[str, str | bool] = {}
                amount = parse_amount(message)
                if amount is not None:
                    entities[INTENT_AMOUNT_FACT[intent]] = amount
                if intent == "calculate_payroll_tax" and pension_flag(message) is False:
                    entities["pension_participant"] = False
                return Extraction(intent=intent, entities=entities, language=language, matched_keywords=hits)
        return Extraction(intent="unknown", language=language)
