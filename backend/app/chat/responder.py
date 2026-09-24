"""Engine results -> a conversational reply. The offline path, and the fallback when a model is unavailable.

Replies answer first (yes/no or the amount), then explain why, then say what's needed next - like an accountant
would. Every fact and number comes from the engine's result; the legal source stays in the result card.
All wording lives in the catalogs in app/i18n/messages (Georgian, English, Russian, German, French).
"""

import re
from typing import Literal

from app.chat.extractor import Extraction
from app.i18n import Language, format_amount, format_date, format_month, t, tlist, tplural
from app.rules.schema import RuleResult, localize

KNOWN_FACTS = {
    "input.gross_salary", "input.taxable_turnover_12m", "company.vat_registered", "input.sale_amount",
    "input.vat_inclusive", "input.distribution_amount", "company.tax_regime",
}
KNOWN_ASSUMPTIONS = {"pension_participant", "dividend_recipient"}

SmallTalk = Literal["greeting", "thanks"]

SMALL_TALK: dict[SmallTalk, re.Pattern] = {
    # Whole words only: "hi" must not match "hire".
    "greeting": re.compile(
        r"^\W*(hi|hello|hey|good (morning|afternoon|evening)"
        r"|გამარჯობათ|გამარჯობა|გაგიმარჯოს|სალამი|ჰაი"
        r"|привет|здравствуйте|здравствуй|добрый (день|вечер)|доброе утро"
        r"|hallo|guten (tag|morgen|abend)|servus|moin"
        r"|bonjour|bonsoir|salut|coucou)\b", re.I),
    "thanks": re.compile(
        r"^\W*(thanks|thank you|thx|მადლობა|გმადლობთ|დიდი მადლობა|спасибо|благодарю|danke|vielen dank|merci)\b",
        re.I),
}


def small_talk(message: str) -> SmallTalk | None:
    for kind, pattern in SMALL_TALK.items():
        if pattern.search(message.strip()):
            return kind
    return None


def suggestions_for(extraction: Extraction, message: str) -> list[str]:
    """Clickable example questions for turns the engine couldn't act on."""
    if extraction.intent != "unknown" or small_talk(message) == "thanks":
        return []
    return tlist("suggestions", extraction.language)


def off_topic_reply(extraction: Extraction, message: str) -> str:
    kind = small_talk(message) or "unknown"
    lang = extraction.language
    lead = t(f"offtopic.{kind}", lang)
    if kind == "thanks":
        return lead
    return lead + "\n" + "\n".join(f"- {s}" for s in tlist("suggestions", lang))


def missing_questions(results: list[RuleResult], language: Language = "en") -> list[str]:
    seen: list[str] = []
    for result in results:
        for fact in result.missing_facts:
            if fact not in seen:
                seen.append(fact)
    return [t(f"fact.{f}", language) if f in KNOWN_FACTS else t("fact.missing", language, fact=f) for f in seen]


def _values(result: RuleResult, lang: Language) -> dict[str, str]:
    return {line.name: format_amount(line.amount, lang) for line in result.breakdown}


def _entity(extraction: Extraction, name: str, lang: Language) -> str:
    return format_amount(extraction.entities.get(name, ""), lang)


def _payroll(results: list[RuleResult], extraction: Extraction, lang: Language) -> list[str] | None:
    result = next((r for r in results if "payroll" in r.rule_id), None)
    if result is None:
        return None
    if result.status == "applies" and result.breakdown:
        v = _values(result, lang)
        in_scheme = extraction.entities.get("pension_participant") is not False
        key = "phrase.payroll_with_pension" if in_scheme else "phrase.payroll_no_pension"
        return [t(key, lang, gross=_entity(extraction, "gross_salary", lang), net=v["net_salary"],
                  tax=v["income_tax"], pension=v["employee_pension"], employer_pension=v["employer_pension"],
                  cost=v["employer_cost"])]
    if result.status == "insufficient_data" and result.missing_facts == ["input.gross_salary"]:
        return [t("phrase.payroll_ask", lang)]
    return None


def _vat_registration(results: list[RuleResult], lang: Language) -> list[str] | None:
    result = next((r for r in results if r.rule_id == "ge.vat.registration_threshold"), None)
    if result is None:
        return None
    if result.status == "applies":
        return [t("phrase.vat_yes", lang)]
    if result.status == "not_applicable":
        return [" ".join([t("phrase.vat_no", lang), *(localize(r, lang) for r in result.reasons)])]
    if result.missing_facts == ["input.taxable_turnover_12m"]:
        return [t("phrase.vat_depends", lang) + " " + t("fact.input.taxable_turnover_12m", lang)]
    return None


def _vat_calculation(results: list[RuleResult], extraction: Extraction, lang: Language) -> list[str] | None:
    result = next((r for r in results if r.rule_id == "ge.vat.output_vat"), None)
    if result is None:
        return None
    if result.status == "applies":
        v = _values(result, lang)
        key = "phrase.vat_inclusive" if extraction.entities.get("vat_inclusive") else "phrase.vat_exclusive"
        return [t(key, lang, gross=v["gross"], vat=v["vat"], net=v["net"])]
    if result.status == "not_applicable":
        return [" ".join([t("phrase.vat_not_registered", lang), *(localize(r, lang) for r in result.reasons)])]
    if result.missing_facts == ["input.vat_inclusive"]:
        return [t("phrase.vat_ask_inclusive", lang, amount=_entity(extraction, "sale_amount", lang))]
    return None


def _distribution(results: list[RuleResult], extraction: Extraction, lang: Language) -> list[str] | None:
    profit = next((r for r in results if r.rule_id == "ge.profit.distribution"), None)
    dividend = next((r for r in results if r.rule_id == "ge.dividend.withholding"), None)
    if profit is None:
        return None
    if profit.status == "insufficient_data" and "input.distribution_amount" in profit.missing_facts:
        return [t("phrase.distribution_ask", lang)]
    if profit.status == "not_applicable":
        return [" ".join(localize(r, lang) for r in profit.reasons)
                or t("phrase.not_applicable", lang, title=localize(profit.title, lang))]
    if profit.status != "applies":
        return None
    v = _values(profit, lang)
    lines = [t("phrase.distribution", lang, amount=_entity(extraction, "distribution_amount", lang),
               profit_tax=v["profit_tax"], cost=v["company_cost"])]
    if dividend is not None and dividend.status == "applies":
        d = _values(dividend, lang)
        lines.append(t("phrase.dividend_withheld", lang, withholding=d["withholding"], net=d["net_dividend"]))
    elif dividend is not None and dividend.status == "not_applicable":
        lines.append(" ".join(localize(r, lang) for r in dividend.reasons))
    return [" ".join(lines)]


def _generic(result: RuleResult, lang: Language) -> str | None:
    title = localize(result.title, lang)
    if result.status == "applies":
        message = localize(result.message, lang)
        if result.amount is not None:
            return t("phrase.applies_amount", lang, title=title, amount=format_amount(result.amount, lang)) + (
                f" {message}" if message else "")
        return message or title
    if result.status == "not_applicable":
        reasons = [localize(r, lang) for r in result.reasons]
        return " ".join(reasons) if reasons else t("phrase.not_applicable", lang, title=title)
    return None  # covered by the follow-up questions


def compose_reply(extraction: Extraction, results: list[RuleResult], message: str = "") -> str:
    lang = extraction.language
    if extraction.intent == "unknown":
        return off_topic_reply(extraction, message)
    if not results:
        return t("phrase.no_rules", lang)

    specific = {
        "calculate_payroll_tax": lambda: _payroll(results, extraction, lang),
        "check_vat_registration": lambda: _vat_registration(results, lang),
        "calculate_vat": lambda: _vat_calculation(results, extraction, lang),
        "calculate_distribution": lambda: _distribution(results, extraction, lang),
    }.get(extraction.intent, lambda: None)()
    lines = specific if specific is not None else [text for r in results if (text := _generic(r, lang))]

    # Intent-specific phrasing asks for what it needs in its own words; only generic answers get the list.
    questions = missing_questions(results, lang) if specific is None else []
    if questions:
        lines += [t("phrase.need", lang)] + [f"- {q}" for q in questions]

    lines += [t(f"assumption.{a}", lang) for a in extraction.assumed if a in KNOWN_ASSUMPTIONS]

    # Only mention verification when the answer actually rests on that rule.
    relevant = [r for r in results if r.status != "insufficient_data"]
    notes = [t(f"verification.{v}", lang) for v in ("demo", "unverified") if any(r.verification == v for r in relevant)]
    if notes:
        lines += [""] + notes
    return "\n".join(lines)


MAX_LISTED = 5


def deadlines_reply(items: list, lang: Language, today) -> str:
    """Upcoming deadlines, soonest first; overdue ones lead. Items are app.api.deadlines.DeadlineItem."""
    if not items:
        return t("deadline.none", lang)
    open_items = [i for i in items if i.state != "done"]
    if not open_items:
        return t("deadline.all_done", lang)
    lines = [t("deadline.intro", lang)]
    for item in open_items[:MAX_LISTED]:
        if item.days_left < 0:
            when = tplural("deadline.overdue", -item.days_left, lang)
        elif item.days_left == 0:
            when = t("deadline.today", lang)
        elif item.days_left == 1:
            when = t("deadline.tomorrow", lang)
        else:
            when = tplural("deadline.in_days", item.days_left, lang)
        monthly = (item.period_start.year, item.period_start.month) == (item.period_end.year, item.period_end.month)
        period = format_month(item.period_start, lang) if monthly else t("deadline.year", lang, year=item.period_start.year)
        lines.append(t("deadline.item", lang, title=localize(item.title, lang), period=period,
                       date=format_date(item.due_date, lang), when=when))
    if len(open_items) > MAX_LISTED:
        lines.append(t("deadline.more", lang, n=len(open_items) - MAX_LISTED))
    lines += ["", t("deadline.unverified", lang)]
    return "\n".join(lines)


class TemplateResponder:
    def compose(self, message: str, extraction: Extraction, results: list[RuleResult]) -> str:
        return compose_reply(extraction, results, message)
