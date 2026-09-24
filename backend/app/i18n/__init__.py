"""Translation catalogs and locale formatting for replies.

Catalogs live in `messages/<lang>.json` (one flat key -> text map per language). A value is a string,
a list (suggestions, month names), or a plural map {"one": ..., "few": ..., "many": ..., "other": ...}.
Rule and deadline texts are not here: they sit next to the rule as {"en": ..., "ka": ...} maps.
"""

import json
import re
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path
from typing import Literal, get_args

Language = Literal["ka", "en", "ru", "de", "fr"]
LANGUAGES: tuple[Language, ...] = get_args(Language)
FALLBACK: Language = "en"
MESSAGES_DIR = Path(__file__).parent / "messages"

# How a language writes 1234567.89 (CLDR conventions).
NUMBER_FORMAT: dict[str, tuple[str, str]] = {  # (group separator, decimal separator)
    "en": (",", "."),
    "ka": (" ", ","),
    "ru": (" ", ","),
    "de": (".", ","),
    "fr": (" ", ","),
}

# English names, for prompts that tell a model which language to write in.
LANGUAGE_NAMES = {"ka": "Georgian", "en": "English", "ru": "Russian", "de": "German", "fr": "French"}

# French puts a narrow no-break space before ? ! : ; and inside guillemets.
_FRENCH_SPACING = re.compile(r" ([?!:;»])|(«) ")


@cache
def catalog(lang: str) -> dict:
    return json.loads((MESSAGES_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def _lookup(key: str, lang: str):
    value = catalog(lang).get(key) if lang in LANGUAGES else None
    return value if value is not None else catalog(FALLBACK)[key]


def _typeset(text: str, lang: str) -> str:
    if lang == "fr":
        return _FRENCH_SPACING.sub(lambda m: f" {m.group(1)}" if m.group(1) else f"{m.group(2)} ", text)
    return text


def t(key: str, lang: str, **values) -> str:
    """The catalog text for `key` in `lang` (English if missing), with {placeholders} filled in."""
    return _typeset(_lookup(key, lang).format(**values), lang)


def tlist(key: str, lang: str) -> list:
    return list(_lookup(key, lang))


def plural_category(n: int, lang: str) -> str:
    """CLDR plural category for an integer."""
    if lang == "ru":
        if n % 10 == 1 and n % 100 != 11:
            return "one"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return "few"
        return "many"
    if lang == "fr":
        return "one" if n in (0, 1) else "other"
    if lang in ("en", "de"):
        return "one" if n == 1 else "other"
    return "other"  # Georgian nouns don't inflect after numerals


def tplural(key: str, n: int, lang: str, **values) -> str:
    forms = _lookup(key, lang)
    if isinstance(forms, str):
        text = forms
    else:
        text = forms.get(plural_category(n, lang)) or forms.get("other") or next(iter(forms.values()))
    return _typeset(text.format(n=n, **values), lang)


def format_amount(value, lang: str) -> str:
    """Group digits and localise the decimal mark of an exact engine value, without changing any digit.

    '2500' -> '2,500' (en) / '2 500' (ka, ru; no-break space) / '2.500' (de); '1960.00' -> '1.960,00' (de).
    """
    text = str(value)
    try:
        Decimal(text)
    except (InvalidOperation, TypeError):
        return text
    group, decimal = NUMBER_FORMAT.get(lang, NUMBER_FORMAT[FALLBACK])
    sign = "-" if text.startswith("-") else ""
    whole, _, frac = text.lstrip("-").partition(".")
    grouped = re.sub(r"(?<=\d)(?=(\d{3})+$)", group, whole)
    return sign + grouped + (decimal + frac if frac else "")


def format_date(day, lang: str) -> str:
    months = tlist("date.months_genitive", lang)
    number = "1er" if lang == "fr" and day.day == 1 else day.day  # French writes "1er avril"
    return t("date.format", lang, day=number, month=months[day.month - 1], year=day.year)


def format_month(day, lang: str) -> str:
    return t("date.month_year", lang, month=tlist("date.months", lang)[day.month - 1], year=day.year)
