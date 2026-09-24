"""Engine results -> a conversational reply. The offline path, and the fallback when a model is unavailable.

Replies answer first (yes/no or the amount), then explain why, then say what's needed next - like an accountant
would. Every fact and number comes from the engine's result; the legal source stays in the result card.
Georgian strings here should get a native speaker's review before real users see them.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Literal

from app.chat.extractor import Extraction, Language
from app.rules.schema import RuleResult, localize

L = dict[Language, str]

FACT_QUESTIONS: dict[str, L] = {
    "input.gross_salary": {
        "en": "What is the gross monthly salary?",
        "ka": "რამდენია თვიური ხელფასი დაბეგვრამდე?",
    },
    "input.taxable_turnover_12m": {
        "en": "What was the total of VAT-taxable sales over the last 12 months?",
        "ka": "რამდენი იყო დღგ-ით დასაბეგრი ოპერაციების ჯამი ბოლო 12 თვის განმავლობაში?",
    },
    "company.vat_registered": {
        "en": "Is the company VAT-registered? You can set this in the company's tax profile.",
        "ka": "რეგისტრირებულია თუ არა კომპანია დღგ-ის გადამხდელად? ეს კომპანიის საგადასახადო პროფილში მიუთითეთ.",
    },
    "company.tax_regime": {
        "en": "Which tax regime is the company on? You can set this in the company's tax profile.",
        "ka": "რომელი საგადასახადო რეჟიმით სარგებლობს კომპანია? ეს საგადასახადო პროფილში მიუთითეთ.",
    },
}

SUGGESTIONS: dict[Language, list[str]] = {
    "en": [
        "I hired someone for GEL 2,500",
        "Our turnover for the last 12 months is 150,000",
        "Do I need to register for VAT?",
    ],
    "ka": [
        "დავიქირავე თანამშრომელი 2500 ლარად",
        "ბოლო 12 თვის ბრუნვა 150 000 ლარია",
        "უნდა დავრეგისტრირდე დღგ-ის გადამხდელად?",
    ],
}

VERIFICATION_NOTES: dict[str, L] = {
    "demo": {
        "en": "Note: this uses a demo rate as a placeholder, not the real Georgian rule yet.",
        "ka": "შენიშვნა: აქ გამოყენებულია სანიმუშო (დემო) განაკვეთი და არა საქართველოს რეალური წესი.",
    },
    "unverified": {
        "en": "This rule was taken from the Tax Code text but hasn't been reviewed by an accountant yet.",
        "ka": "ეს წესი საგადასახადო კოდექსის ტექსტიდანაა აღებული, მაგრამ ბუღალტერს ჯერ არ შეუმოწმებია.",
    },
}

PHRASES: dict[str, L] = {
    # payroll
    "payroll_amount": {
        "en": "For a gross salary of {salary} GEL, the payroll withholding comes to {amount} GEL.",
        "ka": "{salary} ლარიანი ხელფასიდან დასაკავებელი თანხა შეადგენს {amount} ლარს.",
    },
    "payroll_ask": {
        "en": "Sure, I can work that out. What is the gross monthly salary?",
        "ka": "რა თქმა უნდა, დაგითვლით. რამდენია თვიური ხელფასი დაბეგვრამდე?",
    },
    # VAT registration
    "vat_yes": {
        "en": "Yes, you need to register for VAT. Your taxable sales over the last 12 months are above GEL 100 000, "
              "so you have 2 business days to apply to the tax authority (Revenue Service). VAT applies starting "
              "with the sale that took you over the limit.",
        "ka": "დიახ, დღგ-ის გადამხდელად რეგისტრაცია გჭირდებათ. ბოლო 12 თვის დასაბეგრმა ოპერაციებმა 100 000 ლარს "
              "გადააჭარბა, ამიტომ 2 სამუშაო დღის ვადაში უნდა მიმართოთ შემოსავლების სამსახურს. დღგ ვრცელდება იმ "
              "ოპერაციიდან, რომლითაც ზღვარი გადაიჭარბა.",
    },
    "vat_no": {
        "en": "No, you don't need to register.",
        "ka": "არა, რეგისტრაცია არ გჭირდებათ.",
    },
    "vat_depends": {
        "en": "It depends on your turnover. Registration becomes mandatory once taxable sales over any 12 "
              "consecutive months exceed GEL 100 000.",
        "ka": "ეს დამოკიდებულია თქვენს ბრუნვაზე. რეგისტრაცია სავალდებულო ხდება, როგორც კი ნებისმიერი 12 "
              "თანმიმდევრული თვის დასაბეგრი ოპერაციები 100 000 ლარს გადააჭარბებს.",
    },
    # generic
    "applies_amount": {"en": "{title}: {amount} GEL.", "ka": "{title}: {amount} ლარი."},
    "not_applicable": {"en": "{title} doesn't apply here.", "ka": "„{title}“ აქ არ ვრცელდება."},
    "need": {"en": "To answer that I need a bit more information:", "ka": "პასუხისთვის ცოტა მეტი ინფორმაცია მჭირდება:"},
    "no_rules": {
        "en": "I don't have a rule in effect for that on the selected date.",
        "ka": "არჩეული თარიღისთვის ამ საკითხზე მოქმედი წესი არ მაქვს.",
    },
}

SmallTalk = Literal["greeting", "thanks"]

SMALL_TALK: dict[SmallTalk, re.Pattern] = {
    # Whole words only: "hi" must not match "hire".
    "greeting": re.compile(r"^\W*(hi|hello|hey|good (morning|afternoon|evening)|გამარჯობათ|გამარჯობა|გაგიმარჯოს|სალამი|ჰაი)\b", re.I),
    "thanks": re.compile(r"^\W*(thanks|thank you|thx|მადლობა|გმადლობთ|დიდი მადლობა)\b", re.I),
}

OFF_TOPIC: dict[str, L] = {
    "greeting": {
        "en": "Hi! I'm your tax assistant. I can help with payroll tax and VAT registration. For example, ask:",
        "ka": "გამარჯობა! მე ვარ თქვენი საგადასახადო ასისტენტი. შემიძლია დაგეხმაროთ ხელფასის გადასახადისა და "
              "დღგ-ის რეგისტრაციის საკითხებში. მაგალითად, მკითხეთ:",
    },
    "thanks": {
        "en": "You're welcome! Anything else I can check for you?",
        "ka": "არაფრის! კიდევ რამე ხომ არ გაინტერესებთ?",
    },
    "unknown": {
        "en": "I can't answer that one yet. Right now I can help with payroll tax and VAT registration. "
              "Try, for example:",
        "ka": "ამ კითხვაზე პასუხი ჯერ არ შემიძლია. ამჟამად შემიძლია დაგეხმაროთ ხელფასის გადასახადისა და "
              "დღგ-ის რეგისტრაციის საკითხებში. სცადეთ, მაგალითად:",
    },
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
    return SUGGESTIONS[extraction.language]


def off_topic_reply(extraction: Extraction, message: str) -> str:
    kind = small_talk(message) or "unknown"
    lead = OFF_TOPIC[kind][extraction.language]
    if kind == "thanks":
        return lead
    return lead + "\n" + "\n".join(f"- {s}" for s in SUGGESTIONS[extraction.language])


def missing_questions(results: list[RuleResult], language: Language = "en") -> list[str]:
    seen: list[str] = []
    for result in results:
        for fact in result.missing_facts:
            if fact not in seen:
                seen.append(fact)
    missing_text = {"en": "Missing information: {}", "ka": "აკლია ინფორმაცია: {}"}[language]
    return [FACT_QUESTIONS[f][language] if f in FACT_QUESTIONS else missing_text.format(f) for f in seen]


def group_digits(value: str) -> str:
    """'2500' -> '2 500' for reading; the digits themselves are unchanged."""
    try:
        Decimal(value)
    except (InvalidOperation, TypeError):
        return value
    whole, _, frac = value.partition(".")
    grouped = re.sub(r"(?<=\d)(?=(\d{3})+$)", " ", whole)
    return grouped + (f".{frac}" if frac else "")


def _payroll(results: list[RuleResult], extraction: Extraction, lang: Language) -> list[str] | None:
    result = next((r for r in results if "payroll" in r.rule_id), None)
    if result is None:
        return None
    if result.status == "applies" and result.amount is not None:
        salary = group_digits(extraction.entities.get("gross_salary", ""))
        return [PHRASES["payroll_amount"][lang].format(salary=salary, amount=result.amount)]
    if result.status == "insufficient_data" and result.missing_facts == ["input.gross_salary"]:
        return [PHRASES["payroll_ask"][lang]]
    return None


def _vat_registration(results: list[RuleResult], lang: Language) -> list[str] | None:
    result = next((r for r in results if r.rule_id == "ge.vat.registration_threshold"), None)
    if result is None:
        return None
    if result.status == "applies":
        return [PHRASES["vat_yes"][lang]]
    if result.status == "not_applicable":
        return [" ".join([PHRASES["vat_no"][lang], *(localize(r, lang) for r in result.reasons)])]
    if result.missing_facts == ["input.taxable_turnover_12m"]:
        return [PHRASES["vat_depends"][lang] + " " + FACT_QUESTIONS["input.taxable_turnover_12m"][lang]]
    return None


def _generic(result: RuleResult, lang: Language) -> str | None:
    title = localize(result.title, lang)
    if result.status == "applies":
        message = localize(result.message, lang)
        if result.amount is not None:
            return PHRASES["applies_amount"][lang].format(title=title, amount=result.amount) + (
                f" {message}" if message else "")
        return message or title
    if result.status == "not_applicable":
        reasons = [localize(r, lang) for r in result.reasons]
        return " ".join(reasons) if reasons else PHRASES["not_applicable"][lang].format(title=title)
    return None  # covered by the follow-up questions


def compose_reply(extraction: Extraction, results: list[RuleResult], message: str = "") -> str:
    lang = extraction.language
    if extraction.intent == "unknown":
        return off_topic_reply(extraction, message)
    if not results:
        return PHRASES["no_rules"][lang]

    specific = {
        "calculate_payroll_tax": lambda: _payroll(results, extraction, lang),
        "check_vat_registration": lambda: _vat_registration(results, lang),
    }[extraction.intent]()
    lines = specific if specific is not None else [t for r in results if (t := _generic(r, lang))]

    # Follow-up questions the specific phrasing hasn't already asked.
    asked = " ".join(lines)
    questions = [q for q in missing_questions(results, lang) if q not in asked]
    if questions:
        lines += [PHRASES["need"][lang]] + [f"- {q}" for q in questions]

    # Only mention verification when the answer actually rests on that rule.
    relevant = [r for r in results if r.status != "insufficient_data"]
    notes = [VERIFICATION_NOTES[v][lang] for v in ("demo", "unverified") if any(r.verification == v for r in relevant)]
    if notes:
        lines += [""] + notes
    return "\n".join(lines)


class TemplateResponder:
    def compose(self, message: str, extraction: Extraction, results: list[RuleResult]) -> str:
        return compose_reply(extraction, results, message)
