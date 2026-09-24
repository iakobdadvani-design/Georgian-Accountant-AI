"""Score the chat pipeline on evals/cases.json.

    python -m evals.run                         # keyword extractor + template replies (offline, instant)
    python -m evals.run --provider ollama       # local model extracts (replies still templates)
    python -m evals.run --provider ollama --model-replies
    python -m evals.run --provider claude --model-replies   # needs ANTHROPIC_API_KEY; costs money
    python -m evals.run --only vat-incl-ka --verbose

Each case is checked for: intent, extracted facts, the engine's result (status / amount of the named rule),
reply language, and grounding (no number in the reply that the engine or the user didn't produce).
No database: company facts come from the case. Nothing is written except an optional --out JSON report.
"""

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.api.chat import with_defaults
from app.chat.extractor import GEORGIAN, CYRILLIC, INTENT_AMOUNT_FACT, KeywordExtractor, detect_language
from app.chat.llm import AIUnavailable, LLMExtractor, LLMResponder, ungrounded_numbers
from app.chat.responder import TemplateResponder
from app.rules.engine import evaluate, referenced_facts
from app.rules.loader import get_rules

CASES = Path(__file__).parent / "cases.json"
AS_OF = date(2026, 9, 24)
COMPANY = {"company.legal_form": "LLC", "company.vat_registered": False, "company.tax_regime": "standard",
           "company.has_employees": False, "company.owns_property": False, "company.employee_count": 0}
CHECKS = ("intent", "entities", "result", "language", "grounded")


@dataclass
class Outcome:
    case: dict
    passed: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    reply: str = ""
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return all(self.passed.values())


def load_cases(only: str | None = None) -> list[dict]:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case id"
    return [c for c in cases if not only or re.search(only, c["id"])]


def reply_language_ok(reply: str, language: str) -> bool:
    if language == "ka":
        return bool(GEORGIAN.search(reply))
    if language == "ru":
        return bool(CYRILLIC.search(reply)) and not GEORGIAN.search(reply)
    return not GEORGIAN.search(reply) and not CYRILLIC.search(reply) and detect_language(reply, language) == language


def run_case(case: dict, extractor, responder) -> Outcome:
    out = Outcome(case)
    started = time.perf_counter()
    try:
        extraction = extractor.extract(case["message"], "ka")
    except AIUnavailable as e:
        out.notes.append(f"extractor failed: {e}")
        extraction = KeywordExtractor().extract(case["message"], "ka")
    extraction = with_defaults(extraction)

    out.passed["intent"] = extraction.intent == case["intent"]
    if not out.passed["intent"]:
        out.notes.append(f"intent {extraction.intent!r}, expected {case['intent']!r}")
    stated = {k: v for k, v in extraction.entities.items() if k not in extraction.assumed}
    wrong = {k: stated.get(k) for k, v in case["entities"].items() if stated.get(k) != v}
    extra = {k: v for k, v in stated.items() if k not in case["entities"]}
    out.passed["entities"] = not wrong and not extra
    if wrong or extra:
        out.notes.append(f"entities {stated}, expected {case['entities']}")

    results = []
    if extraction.intent in INTENT_AMOUNT_FACT:
        topic = f"input.{INTENT_AMOUNT_FACT[extraction.intent]}"
        rules = [r for r in get_rules() if topic in referenced_facts(r)]
        facts = COMPANY | case.get("company", {}) | {f"input.{k}": v for k, v in extraction.entities.items()}
        results = evaluate(rules, facts, AS_OF)
    if "rule" in case:
        result = next((r for r in results if r.rule_id == case["rule"]), None)
        expected_status = case.get("status", "applies")
        ok = result is not None and result.status == expected_status
        if ok and "amount" in case:
            ok = result.amount == Decimal(case["amount"])
        out.passed["result"] = ok
        if not ok:
            got = f"{result.status} {result.amount}" if result else "no result"
            out.notes.append(f"{case['rule']}: {got}, expected {expected_status} {case.get('amount', '')}".rstrip())
    else:
        out.passed["result"] = True

    if extraction.intent == "list_deadlines":
        out.reply = "(deadline list: dates come from the calendar)"
        out.passed["language"] = out.passed["grounded"] = True
    else:
        try:
            out.reply = responder.compose(case["message"], extraction, results)
        except AIUnavailable as e:
            out.notes.append(f"responder failed: {e}")
            out.reply = TemplateResponder().compose(case["message"], extraction, results)
        out.passed["language"] = reply_language_ok(out.reply, case["language"])
        if not out.passed["language"]:
            out.notes.append(f"reply not in {case['language']}")
        # Templates are fixed catalog text (example questions, "by the 15th"); grounding matters for model replies.
        evidence = case["message"] + json.dumps([r.model_dump(mode="json") for r in results], ensure_ascii=False)
        stray = set() if isinstance(responder, TemplateResponder) else ungrounded_numbers(out.reply, evidence)
        out.passed["grounded"] = not stray
        if stray:
            out.notes.append(f"ungrounded numbers {sorted(map(str, stray))}")
    out.seconds = time.perf_counter() - started
    return out


def pipeline(provider: str, model_replies: bool):
    if provider == "keyword":
        return KeywordExtractor(), TemplateResponder()
    from app.config import settings

    if provider == "ollama":
        from app.chat.ollama import OllamaBackend
        backend = OllamaBackend(settings.ollama_url, settings.ollama_model)
    else:
        from app.chat.claude import ClaudeBackend, get_client
        backend = ClaudeBackend(get_client(), settings.anthropic_model)
    return LLMExtractor(backend), LLMResponder(backend) if model_replies else TemplateResponder()


def summarize(outcomes: list[Outcome]) -> dict:
    def rate(items, check):
        return sum(o.passed[check] for o in items) / len(items) if items else 1.0

    easy = [o for o in outcomes if not o.case.get("hard")]
    return {
        "cases": len(outcomes),
        "passed": sum(o.ok for o in outcomes),
        "passed_excluding_hard": sum(o.ok for o in easy),
        "cases_excluding_hard": len(easy),
        **{f"{c}_accuracy": round(rate(outcomes, c), 3) for c in CHECKS},
        "by_language": {lang: f"{sum(o.ok for o in outcomes if o.case['language'] == lang)}"
                              f"/{sum(1 for o in outcomes if o.case['language'] == lang)}"
                        for lang in ("ka", "en", "ru", "de", "fr")},
        "seconds_per_case": round(sum(o.seconds for o in outcomes) / max(len(outcomes), 1), 2),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=["keyword", "ollama", "claude"], default="keyword")
    parser.add_argument("--model-replies", action="store_true", help="let the model write replies (else templates)")
    parser.add_argument("--only", help="regex on case ids")
    parser.add_argument("--verbose", action="store_true", help="print every reply")
    parser.add_argument("--out", type=Path, help="write a JSON report here")
    parser.add_argument("--min-pass", type=float, default=0.0, help="exit 1 if the non-hard pass rate is lower")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    extractor, responder = pipeline(args.provider, args.model_replies)
    outcomes = []
    for case in load_cases(args.only):
        o = run_case(case, extractor, responder)
        outcomes.append(o)
        mark = "PASS" if o.ok else ("hard" if case.get("hard") else "FAIL")
        print(f"{mark:4}  {case['id']:<26} {' | '.join(o.notes)}")
        if args.verbose:
            print("      " + o.reply.replace("\n", "\n      "))
    summary = summarize(outcomes)
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    if args.out:
        args.out.write_text(json.dumps({"provider": args.provider, "model_replies": args.model_replies, "summary": summary,
                                        "cases": [{"id": o.case["id"], "passed": o.passed, "notes": o.notes, "reply": o.reply}
                                                  for o in outcomes]}, ensure_ascii=False, indent=2), encoding="utf-8")
    rate = summary["passed_excluding_hard"] / max(summary["cases_excluding_hard"], 1)
    return 1 if rate < args.min_pass else 0


if __name__ == "__main__":
    sys.exit(main())
