"""Recording a sale or an expense from the chat ("I sold 1,000 GEL to Nika today", "ჩაწერე ხარჯი 150 ლარი").

The chat only drafts the record; the page shows it and the user presses Save, which posts it like the Sales &
expenses form does. Nothing is written without that confirmation. Parsing only: no amounts are computed here.
"""

import re
from datetime import date, timedelta

from pydantic import BaseModel

from app.chat.extractor import AMOUNT, normalize_amount

# Commands that ask to record something (the keyword extractor needs one; a model understands more). Whole words:
# "recorded sales" and "m'enregistrer à la TVA" (register for VAT) are not requests to write a record.
RECORD_COMMAND = re.compile(
    r"\brecord\b(?!ed)|\badd (a |an )?(sale|expense|income|purchase)\b|\blog (a|an) (sale|expense)|\bwrite down\b"
    r"|ჩაწერე|ჩამიწერე|ჩაიწერე|დაამატე|შეინახე|გაატარე"
    r"|\bзапиши(те)?\b|\bдобавь(те)?\b|\bвнеси(те)?\b|\bзанеси\b"
    r"|\btrag(e)?\b[^.?!]*\bein\b|\berfass(e|en)?\b|\bverbuch(e|en)?\b|\bbuche\b|\bnotier(e|en)?\b"
    r"|\benregistre(z)? (une|un|la|le)\b|\bajoute(z)? (une|un)\b|\bnote(z)? (une|un)\b", re.I)

INCOME = re.compile(
    r"\b(sold|sale|sales|received|got paid|income|revenue|earned|invoice paid|paid me|money in)\b"
    r"|გავყიდე|გაყიდვ|მივიღე|შემოსავ|ჩამირიცხ|შემოვიდა"
    r"|продал|продаж|получил|поступ|доход|выручк"
    r"|verkauf|verkauft|erhalten|einnahme|eingegangen"
    r"|vendu|vente|reçu|recu\b|recette|encaiss", re.I)
EXPENSE = re.compile(
    r"\b(paid|bought|spent|expense|purchase|purchased|rent|bill|money out)\b"
    r"|გადავიხადე|ვიყიდე|ხარჯ|დავხარჯე|ქირა|შევიძინე"
    r"|заплатил|оплатил|купил|потратил|расход|аренд|покупк"
    r"|bezahlt|gezahlt|gekauft|ausgabe|miete|einkauf"
    r"|payé|paye\b|acheté|achete|dépense|depense|loyer|achat", re.I)
PAID_TO_ME = re.compile(r"\b(got paid|paid me|invoice paid|was paid)\b", re.I)

CURRENCIES = [
    ("USD", re.compile(r"\$|\busd\b|dollar|დოლარ|доллар|\bдол\b", re.I)),
    ("EUR", re.compile(r"€|\beur\b|euro|ევრო|евро", re.I)),
    ("GBP", re.compile(r"£|\bgbp\b|pound|ფუნტ|фунт", re.I)),
    ("TRY", re.compile(r"\btry\b|lira|ლირა|лир", re.I)),
    ("RUB", re.compile(r"₽|\brub\b|rouble|ruble|რუბლ|рубл", re.I)),
]

TODAY = re.compile(r"\b(today|heute)\b|დღეს|сегодня|aujourd", re.I)
YESTERDAY = re.compile(r"\b(yesterday|gestern|hier)\b|გუშინ|вчера", re.I)
# Dates need a year when written with dots or slashes, so "12.50" stays an amount.
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DMY_DATE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b")


def direction_of(message: str) -> str | None:
    """'income' or 'expense' when the message says which; None when it doesn't (or says both)."""
    if PAID_TO_ME.search(message):
        return "income"
    income, expense = bool(INCOME.search(message)), bool(EXPENSE.search(message))
    if income != expense:
        return "income" if income else "expense"
    return None


def currency_of(message: str) -> str | None:
    return next((code for code, pattern in CURRENCIES if pattern.search(message)), None)


def date_of(message: str) -> tuple[str | None, list[tuple[int, int]]]:
    """('2026-09-25' | 'today' | 'yesterday' | None, spans the date occupies so its digits aren't read as the amount)."""
    if m := ISO_DATE.search(message):
        return _valid(m.group(1), m.group(2), m.group(3)), [m.span()]
    if m := DMY_DATE.search(message):
        return _valid(m.group(3), m.group(2), m.group(1)), [m.span()]
    if YESTERDAY.search(message):
        return "yesterday", []
    if TODAY.search(message):
        return "today", []
    return None, []


def _valid(year: str, month: str, day: str) -> str | None:
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def record_entities(message: str) -> dict[str, str]:
    found: dict[str, str] = {}
    when, spans = date_of(message)
    inside = lambda s: any(a <= s[0] and s[1] <= b for a, b in spans)
    amounts = [a for m in AMOUNT.finditer(message) if not inside(m.span()) and (a := normalize_amount(m.group(0)))]
    if amounts:
        found["record_amount"] = max(amounts, key=lambda a: float(a))
    if direction := direction_of(message):
        found["record_direction"] = direction
    if currency := currency_of(message):
        found["record_currency"] = currency
    if when:
        found["record_date"] = when
    return found


def resolve_date(value: str | None, as_of: date) -> date:
    if value == "yesterday":
        return as_of - timedelta(days=1)
    if value and value != "today":
        return date.fromisoformat(value)
    return as_of


def missing_for_record(entities: dict) -> list[str]:
    return [f"input.{name}" for name in ("record_direction", "record_amount") if name not in entities]


class TransactionDraft(BaseModel):
    """What the page shows for confirmation and posts to /transactions on Save."""

    occurred_on: date
    direction: str  # "income" | "expense"
    amount: str
    currency: str = "GEL"
    vat_included: bool = False  # the 18% VAT inside the amount (VAT payers); the user can untick it
    vat_payer: bool = False
    description: str | None = None
    date_assumed: bool = False  # no date was given: today was used (the reply says so)


def draft_from(entities: dict, message: str, vat_payer: bool, as_of: date) -> TransactionDraft | None:
    if missing_for_record(entities):
        return None
    return TransactionDraft(
        occurred_on=resolve_date(entities.get("record_date"), as_of), direction=str(entities["record_direction"]),
        amount=str(entities["record_amount"]), currency=str(entities.get("record_currency") or "GEL"),
        vat_included=vat_payer, vat_payer=vat_payer, description=message.strip()[:200] or None,
        date_assumed="record_date" not in entities)


def record_reply(draft: TransactionDraft | None, entities: dict, lang: str) -> str:
    from app.i18n import format_amount, format_date, t

    if draft is None:
        missing = missing_for_record(entities)
        key = "record.ask_both" if len(missing) == 2 else (
            "record.ask_direction" if missing == ["input.record_direction"] else "record.ask_amount")
        return t(key, lang)
    currency = t("record.gel", lang) if draft.currency == "GEL" else draft.currency
    line = t("record.confirm", lang, what=t(f"record.{draft.direction}", lang),
             amount=f"{format_amount(draft.amount, lang)} {currency}", date=format_date(draft.occurred_on, lang))
    if draft.date_assumed:
        line += " " + t("record.today_assumed", lang)
    if draft.currency != "GEL":
        line += " " + t("record.converted", lang)
    return line
