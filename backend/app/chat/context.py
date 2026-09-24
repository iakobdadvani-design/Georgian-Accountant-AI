"""Carry an unfinished question across turns.

When the engine needed a fact ("What is the gross monthly salary?"), the assistant turn stores the pending intent
and entities. A bare follow-up ("2500") then completes that question instead of being classified from scratch.
"""

import re

from app.chat.extractor import INTENT_AMOUNT_FACT, Extraction, Language, parse_amount

LETTER = re.compile(r"[^\W\d_]")


def inherit_language(extraction: Extraction, message: str, previous: Language | None) -> Extraction:
    """A message with no letters ("2500", "150 000") keeps the conversation's language."""
    if previous and previous != extraction.language and not LETTER.search(message):
        return extraction.model_copy(update={"language": previous})
    return extraction


def pending_state(extraction: Extraction, needs_more: bool) -> dict | None:
    if extraction.intent == "unknown" or not needs_more:
        return None
    return {"intent": extraction.intent, "entities": extraction.entities}


def apply_context(extraction: Extraction, message: str, pending: dict | None) -> tuple[Extraction, bool]:
    """Returns the extraction to use and whether earlier turns contributed to it."""
    if not pending:
        return extraction, False
    intent, prior = pending["intent"], pending.get("entities", {})

    if extraction.intent == intent:
        merged = {**prior, **extraction.entities}
        return extraction.model_copy(update={"entities": merged}), merged != extraction.entities

    if extraction.intent == "unknown":
        amount = parse_amount(message)
        if amount is not None:
            entities = {**prior, INTENT_AMOUNT_FACT[intent]: amount}
            return Extraction(intent=intent, entities=entities, language=extraction.language,
                              source=extraction.source), True

    return extraction, False
