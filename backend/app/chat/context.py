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


def topic_state(extraction: Extraction) -> dict | None:
    """What the last answered question was about, so a correction ("they're not in the pension scheme")
    can recompute it. Only facts the user actually stated are kept, never defaults."""
    if extraction.intent == "unknown":
        return None
    stated = {k: v for k, v in extraction.entities.items() if k not in extraction.assumed}
    return {"intent": extraction.intent, "entities": stated}


def apply_context(
    extraction: Extraction, message: str, pending: dict | None, topic: dict | None = None
) -> tuple[Extraction, bool]:
    """Returns the extraction to use and whether earlier turns contributed to it.

    `pending` is an unanswered question; `topic` is the last answered one. A bare amount only ever
    completes a pending question; a same-topic message without an amount reuses the topic's facts.
    """
    base = pending or topic
    if not base:
        return extraction, False
    intent, prior = base["intent"], base.get("entities", {})

    if extraction.intent == intent:
        own_amount = INTENT_AMOUNT_FACT[intent] in extraction.entities
        if pending is None and own_amount:
            return extraction, False  # a new figure on the same topic is a new question
        merged = {**prior, **extraction.entities}
        return extraction.model_copy(update={"entities": merged}), merged != extraction.entities

    if pending is None:
        return extraction, False

    if extraction.intent == "unknown":
        amount = parse_amount(message)
        if amount is not None:
            entities = {**prior, INTENT_AMOUNT_FACT[intent]: amount}
            return Extraction(intent=intent, entities=entities, language=extraction.language,
                              source=extraction.source), True

    return extraction, False
