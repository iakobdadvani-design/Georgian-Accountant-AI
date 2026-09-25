"""Model-agnostic extraction and explanation. A model reads and writes language only; every number comes from the engine.

Backends (Claude, local Ollama) only need to turn (system, user, JSON schema) into a parsed JSON object.
Privacy: only the user's message and the engine's results are sent - no stored company records.
"""

import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Literal, Protocol

from pydantic import BaseModel, ValidationError

from app.chat.extractor import (
    AMOUNT, INTENT_AMOUNT_FACT, SECOND_AMOUNT_FACT, Extraction, Intent, detect_language, normalize_amount,
    vat_inclusive_flag,
)
from app.i18n import LANGUAGE_NAMES, LANGUAGES, Language
from app.rules.schema import RuleResult

log = logging.getLogger(__name__)

Effort = Literal["low", "medium", "high"]


class AIUnavailable(RuntimeError):
    """The model could not produce a usable answer; callers fall back to the offline path."""


class JSONBackend(Protocol):
    name: Literal["claude", "ollama"]
    model: str

    def complete_json(self, system: str, user: str, schema: dict, effort: Effort) -> dict:
        """Return the model's JSON object, or raise AIUnavailable."""
        ...


def parse_json(text: str | None) -> dict:
    try:
        data = json.loads(text or "")
    except json.JSONDecodeError as e:
        raise AIUnavailable("response was not JSON") from e
    if not isinstance(data, dict):
        raise AIUnavailable("response was not a JSON object")
    return data


# --- extraction ---

EXTRACTION_SYSTEM = """You classify messages sent to a Georgian accounting assistant. Messages may be in Georgian, English, Russian, German or French.

Intents:
- calculate_payroll_tax: hiring someone, salaries, wages, payroll withholding.
- check_vat_registration: turnover, revenue or sales volume, or whether the business must register for VAT.
- calculate_vat: how much VAT is on or inside a specific sale, price or invoice.
- calculate_distribution: paying out profit / dividends to owners, or profit tax on a distribution.
- calculate_small_business_tax: tax of an individual entrepreneur with small business status (1% / 3% on income).
- calculate_vat_payable: how much VAT a VAT payer owes for a period after deducting input VAT on purchases.
- list_deadlines: what is due, filing or payment deadlines, the tax calendar.
- unknown: anything else.

amount: the single money amount the user states for that intent, copied as written using only digits, spaces, commas and one decimal point (e.g. "2,500" or "150000"). Do not convert currencies, annualise, add, or otherwise compute. null if no amount is stated.
vat_inclusive: for calculate_vat, true if the stated price already includes VAT, false if VAT comes on top; otherwise null.
dividend_recipient: for calculate_distribution, "company" if the dividend goes to another company, "individual" if to a person; otherwise null.
input_vat: for calculate_vat_payable, the deductible VAT on purchases the user states, copied as written; the VAT on sales goes in amount. null if not stated.
over_small_business_limit: for calculate_small_business_tax, true if the user says gross income this calendar year has exceeded GEL 500 000, false if they say it hasn't; otherwise null.
pension_participant: false only if the user says the employee is not in (or opted out of) the funded pension scheme; true if they say the employee is in it; otherwise null.
language: the language of the message: "ka", "en", "ru", "de" or "fr"."""

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["calculate_payroll_tax", "check_vat_registration", "calculate_vat",
                                              "calculate_distribution", "calculate_small_business_tax",
                                              "calculate_vat_payable", "list_deadlines", "unknown"]},
        "amount": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "pension_participant": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
        "vat_inclusive": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
        "dividend_recipient": {"anyOf": [{"type": "string", "enum": ["individual", "company"]}, {"type": "null"}]},
        "over_small_business_limit": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
        "input_vat": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "language": {"type": "string", "enum": list(LANGUAGES)},
    },
    "required": ["intent", "amount", "pension_participant", "vat_inclusive", "dividend_recipient",
                 "over_small_business_limit", "input_vat", "language"],
    "additionalProperties": False,
}


class _ExtractionOutput(BaseModel):
    intent: Intent
    amount: str | None
    pension_participant: bool | None = None
    vat_inclusive: bool | None = None
    dividend_recipient: Literal["individual", "company"] | None = None
    over_small_business_limit: bool | None = None
    input_vat: str | None = None
    language: Language


class LLMExtractor:
    def __init__(self, backend: JSONBackend):
        self.backend = backend

    def extract(self, message: str, preferred: Language = "en") -> Extraction:
        data = self.backend.complete_json(EXTRACTION_SYSTEM, message, EXTRACTION_SCHEMA, effort="low")
        try:
            out = _ExtractionOutput.model_validate(data)
        except ValidationError as e:
            raise AIUnavailable("extraction did not match schema") from e

        entities: dict[str, str | bool] = {}
        if out.intent == "calculate_payroll_tax" and out.pension_participant is not None:
            entities["pension_participant"] = out.pension_participant
        # Whether a price includes VAT changes the amount, and models guess it when the user didn't say
        # (evals: "I sold goods for 3,000" came back as net). Only the explicit wording counts; otherwise ask.
        if out.intent == "calculate_vat" and (inclusive := vat_inclusive_flag(message)) is not None:
            entities["vat_inclusive"] = inclusive
        # "individual" is the disclosed default anyway; only a stated company recipient is taken from the model.
        if out.intent == "calculate_distribution" and out.dividend_recipient == "company":
            entities["dividend_recipient"] = out.dividend_recipient
        if out.intent == "calculate_small_business_tax" and out.over_small_business_limit is not None:
            entities["over_small_business_limit"] = out.over_small_business_limit
        amounts = {INTENT_AMOUNT_FACT.get(out.intent): out.amount}
        if out.intent in SECOND_AMOUNT_FACT:
            amounts[SECOND_AMOUNT_FACT[out.intent]] = out.input_vat
        for fact, raw in amounts.items():
            if fact is None or raw is None:
                continue
            amount = normalize_amount(raw)
            if amount is None:
                log.warning("Discarding unparseable amount from %s: %r", self.backend.name, raw)
            else:
                entities[fact] = amount
        # Script detection is deterministic; trust it over the model's language field.
        return Extraction(intent=out.intent, entities=entities, language=detect_language(message, preferred),
                          source=self.backend.name)


# --- explanation ---

REPLY_SYSTEM = """You are a friendly, experienced accountant helping a small-business owner in Georgia. A deterministic tax rules engine has already worked out the answer; your job is to explain it the way a good accountant talks to a client.

How to answer:
- Start with the direct answer to their question: "Yes, ...", "No, ...", or the amount.
- Then say why in one or two plain sentences, using the rule's message or reasons. Mention the legal basis once, naturally (e.g. "under Article 165 of the Tax Code"); never list rule IDs, statuses or field names.
- If something is missing, ask for it in a natural way.
- If assumed_by_default lists a fact, say briefly what you assumed and invite a correction. If it is in taken_from_recorded_sales, say it comes from the sales recorded in the app, with that amount.
- Warm and concise, like a person, not a report.

Hard rules:
- Use only numbers that appear in the ENGINE RESULTS or the user's message. Never calculate, estimate, round differently, or introduce any new number.
- The engine is the source of truth. If a result's status is "insufficient_data", ask the user for exactly the facts listed in missing_facts, in plain words.
- Base the legal mention only on each rule's legal_source.citation; never cite anything else.
- verification "demo": say clearly these are demo rules, not real Georgian law. verification "unverified": say the rule was encoded from the Tax Code text but has not yet been reviewed by a qualified accountant.
- Reply in {language_name}. Write amounts the way {language_name} readers expect (for example 1.960,00 in German), never changing a digit. Plain text, no markdown, at most about 100 words."""

REPLY_SCHEMA = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}

def numbers_in(text: str) -> set[Decimal]:
    """Every number in the text, read in any of the supported locales (1,960.00 / 1.960,00 / 1 960,00)."""
    found = set()
    for match in AMOUNT.finditer(text):
        value = normalize_amount(match.group(0))
        if value is not None:
            try:
                found.add(Decimal(value))
            except InvalidOperation:
                continue
    return found


def ungrounded_numbers(reply: str, evidence: str) -> set[Decimal]:
    """Numbers in the reply that appear nowhere in the evidence.

    Allowed besides exact matches: single-digit integers (counts, list items) and a rate restated as a
    percentage (0.12 in the evidence permits "12%").
    """
    allowed = numbers_in(evidence)
    allowed |= {n * 100 for n in allowed if 0 < n < 1}
    return {n for n in numbers_in(reply) if n not in allowed and not (n == n.to_integral() and n < 10)}


class LLMResponder:
    def __init__(self, backend: JSONBackend):
        self.backend = backend

    def compose(self, message: str, extraction: Extraction, results: list[RuleResult]) -> str:
        payload = json.dumps({
            "intent": extraction.intent,
            "entities": extraction.entities,
            "assumed_by_default": extraction.assumed,
            "taken_from_recorded_sales": extraction.from_books,
            "results": [r.model_dump(mode="json", exclude={"citations"}) for r in results],
        }, ensure_ascii=False)
        user = f"USER MESSAGE:\n{message}\n\nENGINE RESULTS:\n{payload}"
        system = REPLY_SYSTEM.format(language_name=LANGUAGE_NAMES[extraction.language])

        data = self.backend.complete_json(system, user, REPLY_SCHEMA, effort="medium")
        reply = data.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            raise AIUnavailable("empty reply")

        stray = ungrounded_numbers(reply, user)
        if stray:
            raise AIUnavailable(f"reply contained numbers not produced by the engine: {sorted(map(str, stray))}")
        return reply.strip()
