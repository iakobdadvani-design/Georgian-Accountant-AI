"""Message -> structured intent + entities. The AI layer's only job on the way in; it never computes tax.

Understands Georgian, English, Russian, German and French. Keywords are prefixes ("hire" matches "hired");
a trailing "$" makes one a whole word ("umsatz$" must not match "Umsatzsteuer").
"""

import re
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel

from app.i18n import Language

Intent = Literal[
    "calculate_payroll_tax", "check_vat_registration", "calculate_vat", "calculate_distribution", "list_deadlines",
    "unknown",
]

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
    def extract(self, message: str, preferred: Language = "en") -> Extraction: ...


# Checked in order; the first group with a hit wins. Registration words beat VAT-amount words
# ("register for VAT"), and a bare "VAT" only means registration when nothing more specific matched.
KEYWORDS: list[tuple[Intent, list[str]]] = [
    ("list_deadlines", [
        "deadline", "due", "calendar", "what do i need to file",
        "ვადა", "ვადებ", "ვადის", "კალენდარ", "დეკლარაცი", "რა უნდა ჩავაბარო", "როდის უნდა გადავიხადო",
        "срок", "дедлайн", "календар", "декларац", "когда платить", "когда подавать",
        "frist", "fällig", "termin", "kalender", "steuererklärung", "erklärung", "abgabe",
        "échéance", "echeance", "délai", "date limite", "calendrier", "déclaration",
    ]),
    ("calculate_distribution", [
        "dividend", "distribut", "pay out profit", "profit tax",
        "დივიდენდ", "განაწილ", "მოგების გადასახად",
        "дивиденд", "распредел", "налог на прибыль",
        "ausschütt", "gewinnausschütt", "gewinnsteuer", "körperschaftsteuer",
        "distribu", "impôt sur les bénéfices", "impot sur les benefices",
    ]),
    ("calculate_payroll_tax", [
        "salary", "payroll", "wage", "hired", "hire", "employee", "pension",
        "ხელფას", "დავიქირავე", "თანამშრომ", "საპენსიო", "პენსი",
        "зарплат", "заработн", "оклад", "нанял", "нанять", "сотрудник", "работник", "пенси",
        "gehalt", "gehält", "lohn", "löhne", "eingestellt", "einstellen", "mitarbeiter", "angestellt", "arbeitnehmer",
        "rente",
        "salaire", "salarié", "embauch", "employé", "paie", "retraite",
    ]),
    ("check_vat_registration", [
        "regist", "turnover", "revenue",
        "რეგისტრ", "ბრუნვ", "შემოსავ",
        "регистр", "оборот", "выручк",
        "registrier", "anmeld", "umsatz$", "umsätze", "jahresumsatz",
        "enregistr", "immatricul", "assujetti", "chiffre d'affaires", "chiffre d’affaires",
    ]),
    ("calculate_vat", [
        "invoice", "how much vat", "vat on", "vat for", "vat in", "vat amount", "price", "sold", "sell",
        "including vat", "incl", "excluding vat", "excl", "plus vat",
        "ინვოის", "ანგარიშ-ფაქტ", "ფასი", "გავყიდე", "ვყიდი", "რამდენი დღგ", "დღგ რამდენ", "ჩათვლით", "გარეშე",
        "счет", "счёт", "цен", "стоимост", "продал", "сколько ндс", "ндс с ", "ндс на", "включая ндс", "с ндс",
        "без ндс", "плюс ндс",
        "rechnung", "preis", "verkauft", "wie viel mwst", "wie viel mehrwertsteuer", "wie viel umsatzsteuer",
        "wie viel ust", "mwst auf", "mehrwertsteuer auf", "umsatzsteuer auf", "ust auf", "inkl", "zzgl", "zuzüglich",
        "exkl", "brutto", "netto", "ohne mwst",
        "facture", "prix", "vendu", "combien de tva", "tva sur", "ttc$", "ht$", "hors taxe", "hors tva",
        "tva comprise", "tva incluse",
    ]),
    ("check_vat_registration", [
        "vat", "sales", "დღგ", "ндс", "продаж", "mwst", "mehrwertsteuer", "umsatzsteuer", "ust$", "verkäufe",
        "tva", "ventes",
    ]),
]

# "not in the pension scheme", "საპენსიოში არ არის", "не участвует в пенсионной", "nicht in der Rente", "pas de retraite"
NO_PENSION = re.compile(
    r"\b(not|isn't|isnt|no longer|opted out|opt(ed)? out|without|no)\b[^.?!]{0,30}\bpension"
    r"|\bpension\b[^.?!]{0,20}\b(opted out|exempt)"
    r"|\bარ\b[^.?!]{0,25}(საპენსიო|პენსი)|(საპენსიო|პენსი)[^.?!]{0,25}\bარ\b"
    r"|\bне\b[^.?!]{0,30}пенси|без\s+пенси|пенси\w*[^.?!]{0,20}\bне\b"
    r"|\b(kein|keine|keinen|nicht|ohne)\b[^.?!]{0,30}(rente|pension)"
    r"|\b(pas|sans|non)\b[^.?!]{0,30}(retraite|pension)",
    re.I,
)

NOT_INCLUDED = re.compile(
    r"\b(excl|excluding|without|before|plus|net of|not includ|doesn'?t include|does not include)\b[^.?!]{0,15}\bvat\b"
    r"|\+\s*vat|\bnet\b|\bvat\b[^.?!]{0,15}\b(on top|extra|excluded|not included)"
    r"|დღგ-?(ის|ს)?\s*(გარეშე|გარდა)|\+\s*დღგ|პლუს\s+დღგ|დღგ-ს\s+არ\s+შეიცავს"
    r"|без\s+ндс|плюс\s+ндс|\+\s*ндс|не\s+включая\s+ндс|ндс\s+сверху|ндс\s+не\s+включ"
    r"|\b(zzgl|zuzüglich|exkl|exklusive|ohne|plus|netto)\b\.?[^.?!]{0,10}(mwst|ust\b|mehrwertsteuer|umsatzsteuer)"
    r"|\bnetto\b"
    r"|\bht\b|hors\s+(taxes?|tva)|\+\s*tva|plus\s+(la\s+)?tva|sans\s+(la\s+)?tva|tva\s+en\s+sus",
    re.I,
)
INCLUDED = re.compile(
    r"\b(incl|including|includes|included|inclusive|with)\b[^.?!]{0,15}\bvat\b|\bvat\b[^.?!]{0,10}\b(included|inclusive)"
    r"|\bgross\b|დღგ-?(ის|ს)?\s*ჩათვლით|დღგ-ით|დღგ-ს\s+შეიცავს"
    r"|(включая|с\s+учетом|с\s+учётом|в\s+том\s+числе)\s+ндс|\bс\s+ндс\b|ндс\s+включ"
    r"|\b(inkl|inklusive|einschließlich|einschl|mit)\b\.?[^.?!]{0,10}(mwst|ust\b|mehrwertsteuer|umsatzsteuer)"
    r"|\bbrutto\b|(mwst|mehrwertsteuer)\.?\s+(inklusive|enthalten|inbegriffen)"
    r"|\bttc\b|tva\s+(comprise|incluse)|toutes\s+taxes\s+comprises|(avec|y\s+compris)\s+(la\s+)?tva",
    re.I,
)
YES = re.compile(r"^\W*(yes|yeah|yep|yup|correct|right|it does|sure|კი|დიახ|ჰო|ხო|კაი"
                 r"|да|ага|конечно|верно|включает|ja|jawohl|genau|doch|stimmt|oui|ouais|exact|bien sûr)\b", re.I)
NO = re.compile(r"^\W*(no|nope|not|it doesn'?t|არა|არ|нет|не|nein|nee|non)\b", re.I)
TO_COMPANY = re.compile(
    r"\b(to|for) (a|an|another|our|the|my)? ?(company|llc|parent|holding|enterprise)\b"
    r"|კომპანიას|საწარმოს|შპს-ს|ჰოლდინგ"
    r"|компани[июя]\b|предприяти[юя]\b|холдинг|материнск"
    r"|\b(an|für)\s+(die|eine|unsere|unserer)?\s*(gesellschaft|firma|muttergesellschaft|holding|gmbh)\b"
    r"|muttergesellschaft"
    r"|\b(à|a)\s+(une|notre|la)?\s*(société|entreprise|holding)\b|société mère|maison mère",
    re.I,
)


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


# --- language ---

GEORGIAN = re.compile(r"[Ⴀ-ჿ]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
LATIN_LANGUAGES = ("en", "de", "fr")
# Letters and short words that give a Latin-script message away.
LETTER_HINTS = {"de": re.compile(r"[äöüß]", re.I), "fr": re.compile(r"[éèêëàâçùûôœ]", re.I)}
WORD_HINTS = {
    "en": {"the", "and", "is", "for", "how", "much", "i", "we", "our", "my", "do", "need", "what", "salary", "hired"},
    "de": {"der", "die", "das", "und", "ist", "ich", "wir", "wie", "viel", "für", "mit", "unser", "muss", "gehalt",
           "habe", "einen", "eine"},
    "fr": {"le", "la", "les", "et", "est", "je", "nous", "pour", "combien", "du", "des", "notre", "dois", "salaire",
           "un", "une", "quel"},
}


def detect_language(message: str, preferred: Language = "en") -> Language:
    """Script decides Georgian and Russian; for Latin script, clear hints win, otherwise the user's chosen language."""
    if GEORGIAN.search(message):
        return "ka"
    if CYRILLIC.search(message):
        return "ru"
    for lang, pattern in LETTER_HINTS.items():
        if pattern.search(message):
            return lang
    words = set(re.findall(r"[a-z']+", message.lower()))
    scores = {lang: len(words & hints) for lang, hints in WORD_HINTS.items()}
    best = max(scores, key=scores.get)
    if scores[best] and list(scores.values()).count(scores[best]) == 1:
        return best
    return preferred if preferred in LATIN_LANGUAGES else "en"


# --- amounts ---
# Money never has three decimals, so any separator followed by exactly three digits groups thousands:
# 2500 | 2,500 | 2.500 | 2 500 | 2'500 -> 2500;  2500.50 | 2500,50 -> 2500.50;  1.234.567,89 | 1,234,567.89
_SEPARATORS = " ,.'  "
AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:[" + _SEPARATORS + r"]\d{3})+|\d+)(?:[.,](\d{1,2}))?(?![\d])")


def normalize_amount(raw: str) -> str | None:
    """'2,500' / '2.500' / '2 500' / '2500,50' -> exact decimal string; None if it isn't a plain amount."""
    match = AMOUNT.fullmatch(raw.strip())
    if match is None:
        return None
    whole = re.sub("[" + _SEPARATORS + "]", "", match.group(1))
    return str(Decimal(f"{whole}.{match.group(2)}" if match.group(2) else whole))


def parse_amount(message: str) -> str | None:
    """Largest amount in the message as an exact decimal string, or None.

    Largest, not first: in "turnover for the last 12 months is 150,000" the 12 is a period, not the amount.
    """
    amounts = [normalize_amount(m.group(0)) for m in AMOUNT.finditer(message)]
    return max((a for a in amounts if a is not None), key=Decimal, default=None)


def _keyword_hits(words: list[str], text: str) -> list[str]:
    hits = []
    for word in words:
        whole = word.endswith("$")
        pattern = r"\b" + re.escape(word.rstrip("$")) + (r"\b" if whole else "")
        if re.search(pattern, text):
            hits.append(word)
    return hits


class KeywordExtractor:
    """Offline fallback: first intent group with a keyword hit wins."""

    def extract(self, message: str, preferred: Language = "en") -> Extraction:
        text = message.lower()
        language = detect_language(message, preferred)
        for intent, words in KEYWORDS:
            hits = _keyword_hits(words, text)
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
