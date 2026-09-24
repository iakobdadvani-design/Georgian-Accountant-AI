"""The answer-quality set (evals/cases.json) with the offline pipeline: every non-"hard" case must pass.

"hard" cases are casual phrasings keyword matching isn't expected to get; a model extractor should. Run
`python -m evals.run --provider ollama` (or claude) to score one.
"""

from evals.run import load_cases, run_case, summarize
from app.chat.extractor import KeywordExtractor
from app.chat.responder import TemplateResponder


def test_offline_pipeline_passes_every_non_hard_case():
    outcomes = [run_case(c, KeywordExtractor(), TemplateResponder()) for c in load_cases()]
    failing = {o.case["id"]: o.notes for o in outcomes if not o.ok and not o.case.get("hard")}
    assert failing == {}
    summary = summarize(outcomes)
    assert summary["cases"] >= 50 and set(summary["by_language"]) == {"ka", "en", "ru", "de", "fr"}


def test_cases_cover_every_intent_and_language():
    cases = load_cases()
    from app.chat.extractor import Intent
    from typing import get_args
    assert {c["intent"] for c in cases} == set(get_args(Intent))
    for lang in ("ka", "en", "ru", "de", "fr"):
        assert sum(c["language"] == lang for c in cases) >= 5
