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
    "input.sale_amount": {
        "en": "What is the amount of the sale or invoice?",
        "ka": "რა თანხაზეა რეალიზაცია ან ინვოისი?",
    },
    "input.vat_inclusive": {
        "en": "Does that amount already include VAT?",
        "ka": "ეს თანხა უკვე შეიცავს დღგ-ს?",
    },
    "input.distribution_amount": {
        "en": "How much do you want to pay out as dividends?",
        "ka": "რა თანხის გაცემა გსურთ დივიდენდის სახით?",
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
        "How much VAT is in 11,800 GEL including VAT?",
        "We want to pay 8,500 GEL in dividends",
    ],
    "ka": [
        "დავიქირავე თანამშრომელი 2500 ლარად",
        "ბოლო 12 თვის ბრუნვა 150 000 ლარია",
        "უნდა დავრეგისტრირდე დღგ-ის გადამხდელად?",
        "რამდენია დღგ 11 800 ლარში დღგ-ს ჩათვლით?",
        "გვინდა 8 500 ლარი გავცეთ დივიდენდად",
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
    "payroll_with_pension": {
        "en": "For a gross salary of {gross} GEL, the employee takes home {net} GEL. You withhold {pension} GEL "
              "for their pension (2%) and {tax} GEL income tax (20% of what's left). On top of the salary you also "
              "pay a {employer_pension} GEL employer pension contribution, so this salary costs you {cost} GEL in "
              "total.",
        "ka": "{gross} ლარიანი ხელფასიდან თანამშრომელს ხელზე დარჩება {net} ლარი. თქვენ აკავებთ {pension} ლარს "
              "საპენსიო შენატანად (2%) და {tax} ლარს საშემოსავლო გადასახადად (დარჩენილი თანხის 20%). ამას გარდა, "
              "თავად იხდით {employer_pension} ლარს დამსაქმებლის საპენსიო შენატანად, ასე რომ, ეს ხელფასი ჯამში "
              "{cost} ლარი დაგიჯდებათ.",
    },
    "payroll_no_pension": {
        "en": "For a gross salary of {gross} GEL, the employee takes home {net} GEL after {tax} GEL income tax (20%). "
              "No pension contributions apply, since they're not in the funded pension scheme.",
        "ka": "{gross} ლარიანი ხელფასიდან თანამშრომელს ხელზე დარჩება {net} ლარი, {tax} ლარის საშემოსავლო "
              "გადასახადის (20%) გამოკლების შემდეგ. საპენსიო შენატანი არ ერიცხება, რადგან დაგროვებით საპენსიო "
              "სქემაში არ მონაწილეობს.",
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
    # VAT on a sale
    "vat_inclusive": {
        "en": "{gross} GEL including VAT contains {vat} GEL of VAT, so the price without VAT is {net} GEL. "
              "(VAT is 18% of the net price, which is 18/118 of a VAT-inclusive total.)",
        "ka": "{gross} ლარი დღგ-ს ჩათვლით შეიცავს {vat} ლარის დღგ-ს, ასე რომ, ფასი დღგ-ის გარეშე არის {net} ლარი. "
              "(დღგ არის წმინდა ფასის 18%, ანუ დღგ-ს ჩათვლით ჯამის 18/118.)",
    },
    "vat_exclusive": {
        "en": "VAT at 18% on {net} GEL is {vat} GEL, so the total with VAT is {gross} GEL.",
        "ka": "{net} ლარზე 18%-იანი დღგ შეადგენს {vat} ლარს, ასე რომ, ჯამი დღგ-ს ჩათვლით არის {gross} ლარი.",
    },
    "vat_not_registered": {"en": "There's no VAT to add.", "ka": "დღგ-ს დარიცხვა არ გიწევთ."},
    "vat_ask_inclusive": {
        "en": "Sure. Does {amount} GEL already include VAT, or does VAT come on top?",
        "ka": "რა თქმა უნდა. {amount} ლარი უკვე შეიცავს დღგ-ს, თუ დღგ ზემოდან ემატება?",
    },
    # profit distribution
    "distribution": {
        "en": "If the company pays out {amount} GEL in dividends, it owes {profit_tax} GEL profit tax: the payout "
              "is grossed up (divided by 0.85) and taxed at 15%, so the distribution costs the company {cost} GEL in "
              "total.",
        "ka": "თუ კომპანია დივიდენდად გასცემს {amount} ლარს, მოგების გადასახადი იქნება {profit_tax} ლარი: გასაცემი "
              "თანხა იყოფა 0.85-ზე და იბეგრება 15%-ით, ასე რომ, განაწილება კომპანიას ჯამში {cost} ლარი დაუჯდება.",
    },
    "dividend_withheld": {
        "en": "When paying it, you withhold {withholding} GEL dividend tax (5%), so the owner receives {net} GEL.",
        "ka": "გაცემისას აკავებთ {withholding} ლარს დივიდენდის გადასახადად (5%), ასე რომ, მესაკუთრე მიიღებს {net} ლარს.",
    },
    "distribution_ask": {
        "en": "In Georgia a company pays profit tax only when it distributes profit, not while it keeps it. The "
              "payout is divided by 0.85 and taxed at 15%, and 5% is withheld from dividends paid to individuals. "
              "How much do you want to pay out?",
        "ka": "საქართველოში კომპანია მოგების გადასახადს იხდის მხოლოდ მოგების განაწილებისას და არა მაშინ, როცა "
              "მოგებას ინარჩუნებს. გასაცემი თანხა იყოფა 0.85-ზე და იბეგრება 15%-ით, ფიზიკური პირისთვის გაცემულ "
              "დივიდენდს კი 5% ეკავება. რა თანხის გაცემა გსურთ?",
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

ASSUMPTIONS: dict[str, L] = {
    "dividend_recipient": {
        "en": "I've assumed the dividend goes to an individual owner. Dividends paid to another company aren't taxed "
              "at source, so tell me if that's the case.",
        "ka": "ვივარაუდე, რომ დივიდენდს ფიზიკური პირი (მესაკუთრე) იღებს. სხვა კომპანიისთვის გადახდილი დივიდენდი "
              "წყაროსთან არ იბეგრება, ასე რომ, თუ ასეა, მითხარით.",
    },
    "pension_participant": {
        "en": "I've assumed the employee is in the funded pension scheme, as most employees are. Tell me if they're not.",
        "ka": "ვივარაუდე, რომ თანამშრომელი დაგროვებით საპენსიო სქემაშია ჩართული, როგორც დასაქმებულთა უმეტესობა. "
              "თუ ასე არ არის, მითხარით.",
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
        "en": "Hi! I'm your tax assistant. I can help with salaries, VAT and dividends. For example, ask:",
        "ka": "გამარჯობა! მე ვარ თქვენი საგადასახადო ასისტენტი. შემიძლია დაგეხმაროთ ხელფასის, დღგ-ისა და "
              "დივიდენდის საკითხებში. მაგალითად, მკითხეთ:",
    },
    "thanks": {
        "en": "You're welcome! Anything else I can check for you?",
        "ka": "არაფრის! კიდევ რამე ხომ არ გაინტერესებთ?",
    },
    "unknown": {
        "en": "I can't answer that one yet. Right now I can help with salaries, VAT and dividends. "
              "Try, for example:",
        "ka": "ამ კითხვაზე პასუხი ჯერ არ შემიძლია. ამჟამად შემიძლია დაგეხმაროთ ხელფასის, დღგ-ისა და "
              "დივიდენდის საკითხებში. სცადეთ, მაგალითად:",
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
    if result.status == "applies" and result.breakdown:
        values = {line.name: group_digits(str(line.amount)) for line in result.breakdown}
        gross = group_digits(str(extraction.entities.get("gross_salary", "")))
        in_scheme = extraction.entities.get("pension_participant") is not False
        key = "payroll_with_pension" if in_scheme else "payroll_no_pension"
        return [PHRASES[key][lang].format(gross=gross, net=values["net_salary"], tax=values["income_tax"],
                                          pension=values["employee_pension"],
                                          employer_pension=values["employer_pension"], cost=values["employer_cost"])]
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


def _values(result: RuleResult) -> dict[str, str]:
    return {line.name: group_digits(str(line.amount)) for line in result.breakdown}


def _vat_calculation(results: list[RuleResult], extraction: Extraction, lang: Language) -> list[str] | None:
    result = next((r for r in results if r.rule_id == "ge.vat.output_vat"), None)
    if result is None:
        return None
    if result.status == "applies":
        v = _values(result)
        key = "vat_inclusive" if extraction.entities.get("vat_inclusive") else "vat_exclusive"
        return [PHRASES[key][lang].format(gross=v["gross"], vat=v["vat"], net=v["net"])]
    if result.status == "not_applicable":
        return [" ".join([PHRASES["vat_not_registered"][lang], *(localize(r, lang) for r in result.reasons)])]
    if result.missing_facts == ["input.vat_inclusive"]:
        amount = group_digits(str(extraction.entities.get("sale_amount", "")))
        return [PHRASES["vat_ask_inclusive"][lang].format(amount=amount)]
    return None


def _distribution(results: list[RuleResult], extraction: Extraction, lang: Language) -> list[str] | None:
    profit = next((r for r in results if r.rule_id == "ge.profit.distribution"), None)
    dividend = next((r for r in results if r.rule_id == "ge.dividend.withholding"), None)
    if profit is None:
        return None
    if profit.status == "insufficient_data" and "input.distribution_amount" in profit.missing_facts:
        return [PHRASES["distribution_ask"][lang]]
    if profit.status == "not_applicable":
        return [" ".join(localize(r, lang) for r in profit.reasons) or PHRASES["not_applicable"][lang].format(
            title=localize(profit.title, lang))]
    if profit.status != "applies":
        return None
    v = _values(profit)
    amount = group_digits(str(extraction.entities.get("distribution_amount", "")))
    lines = [PHRASES["distribution"][lang].format(amount=amount, profit_tax=v["profit_tax"], cost=v["company_cost"])]
    if dividend is not None and dividend.status == "applies":
        d = _values(dividend)
        lines.append(PHRASES["dividend_withheld"][lang].format(withholding=d["withholding"], net=d["net_dividend"]))
    elif dividend is not None and dividend.status == "not_applicable":
        lines.append(" ".join(localize(r, lang) for r in dividend.reasons))
    return [" ".join(lines)]


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
        "calculate_vat": lambda: _vat_calculation(results, extraction, lang),
        "calculate_distribution": lambda: _distribution(results, extraction, lang),
    }[extraction.intent]()
    lines = specific if specific is not None else [t for r in results if (t := _generic(r, lang))]

    # Intent-specific phrasing asks for what it needs in its own words; only generic answers get the list.
    questions = missing_questions(results, lang) if specific is None else []
    if questions:
        lines += [PHRASES["need"][lang]] + [f"- {q}" for q in questions]

    lines += [ASSUMPTIONS[a][lang] for a in extraction.assumed if a in ASSUMPTIONS]

    # Only mention verification when the answer actually rests on that rule.
    relevant = [r for r in results if r.status != "insufficient_data"]
    notes = [VERIFICATION_NOTES[v][lang] for v in ("demo", "unverified") if any(r.verification == v for r in relevant)]
    if notes:
        lines += [""] + notes
    return "\n".join(lines)


class TemplateResponder:
    def compose(self, message: str, extraction: Extraction, results: list[RuleResult]) -> str:
        return compose_reply(extraction, results, message)
