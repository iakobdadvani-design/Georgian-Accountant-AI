"""Read a bank statement (CSV or .xlsx) into transactions.

No bank's format is hard-coded: the header row is found by its column names (Georgian, English, Russian, German,
French), the user can correct the guessed columns, and each row gets a fingerprint so re-importing the same
statement adds nothing. Parsing only; nothing here computes tax.
"""

import csv
import hashlib
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel

from app.models.enums import TransactionDirection

MAX_ROWS = 5000
HEADER_SCAN_ROWS = 25
Column = Literal["date", "amount", "income", "expense", "description", "counterparty"]
COLUMNS: tuple[Column, ...] = ("date", "amount", "income", "expense", "description", "counterparty")

# Lower-case fragments of header names. Checked in this order, so "debit amount" is an expense column,
# not the signed amount column.
HEADER_WORDS: dict[Column, tuple[str, ...]] = {
    "income": ("credit", "კრედიტ", "შემოსავ", "ჩარიცხ", "შემოსულ", "приход", "кредит", "поступлен", "зачислен",
               "haben", "eingang", "gutschrift", "crédit", "entrée", "money in", "paid in", "inflow"),
    "expense": ("debit", "დებეტ", "გასავ", "ჩამოჭრ", "გასულ", "расход", "дебет", "списан", "soll", "ausgang",
                "belastung", "débit", "sortie", "money out", "paid out", "outflow"),
    "date": ("date", "თარიღ", "дата", "datum"),
    "amount": ("amount", "თანხა", "сумма", "betrag", "montant"),
    "counterparty": ("counterparty", "partner", "beneficiary", "payer", "payee", "კონტრაგენტ", "მიმღებ",
                     "გამგზავნ", "პარტნიორ", "გადამხდ", "контрагент", "получател", "плательщик", "empfänger",
                     "auftraggeber", "bénéficiaire", "tiers"),
    "description": ("description", "details", "purpose", "narrative", "reference", "დანიშნულ", "აღწერ", "შინაარს",
                    "назначени", "описани", "verwendungszweck", "beschreibung", "buchungstext", "libellé", "libelle",
                    "motif"),
}


class ImportError_(ValueError):
    """The file can't be read as a statement. The message is a key for the UI catalog."""


class ParsedRow(BaseModel):
    row: int  # 1-based row number in the file
    occurred_on: date
    direction: TransactionDirection
    amount: Decimal
    description: str | None = None
    counterparty: str | None = None
    external_id: str


class SkippedRow(BaseModel):
    row: int
    reason: Literal["no_date", "no_amount", "zero"]


@dataclass
class Table:
    rows: list[list[str]]
    header_row: int  # index into rows
    mapping: dict[Column, int | None]

    @property
    def header(self) -> list[str]:
        return self.rows[self.header_row]


# ---------- reading files ----------

def read_rows(filename: str, content: bytes) -> list[list[str]]:
    if filename.lower().endswith(".xlsx") or content[:2] == b"PK":
        return _read_xlsx(content)
    return _read_csv(content)


def _read_csv(content: bytes) -> list[list[str]]:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ImportError_("import.error.encoding")
    sample = text[:5000]
    delimiter = max(",;\t|", key=lambda d: sample.count(d))
    rows = [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(text), delimiter=delimiter)]
    return [r for r in rows if any(r)][:MAX_ROWS + HEADER_SCAN_ROWS]


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _read_xlsx(content: bytes) -> list[list[str]]:
    """First worksheet of an .xlsx file, as text. Dates stored as serial numbers stay numbers (see parse_date)."""
    try:
        book = zipfile.ZipFile(io.BytesIO(content))
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            for item in ET.fromstring(book.read("xl/sharedStrings.xml")).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in item.iter(f"{{{NS['m']}}}t")))
        sheet_path = _first_sheet(book)
        sheet = ET.fromstring(book.read(sheet_path))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        raise ImportError_("import.error.unreadable") from e

    rows = []
    for row in sheet.iter(f"{{{NS['m']}}}row"):
        cells: dict[int, str] = {}
        for cell in row.findall("m:c", NS):
            col = _column_index(cell.get("r", ""))
            kind, value = cell.get("t"), cell.find("m:v", NS)
            if kind == "s" and value is not None:
                text = shared[int(value.text)]
            elif kind == "inlineStr":
                text = "".join(t.text or "" for t in cell.iter(f"{{{NS['m']}}}t"))
            else:
                text = value.text if value is not None and value.text else ""
            cells[col if col is not None else len(cells)] = text.strip()
        if any(cells.values()):
            width = max(cells) + 1
            rows.append([cells.get(i, "") for i in range(width)])
        if len(rows) >= MAX_ROWS + HEADER_SCAN_ROWS:
            break
    return rows


def _first_sheet(book: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    first = workbook.find("m:sheets/m:sheet", NS)
    rel_id = first.get(f"{{{REL_NS}}}id") if first is not None else None
    if rel_id and "xl/_rels/workbook.xml.rels" in book.namelist():
        for rel in ET.fromstring(book.read("xl/_rels/workbook.xml.rels")):
            if rel.get("Id") == rel_id:
                target = rel.get("Target", "").lstrip("/")
                return target if target.startswith("xl/") else f"xl/{target}"
    return "xl/worksheets/sheet1.xml"


def _column_index(ref: str) -> int | None:
    letters = re.match(r"[A-Z]+", ref)
    if not letters:
        return None
    index = 0
    for ch in letters.group(0):
        index = index * 26 + ord(ch) - 64
    return index - 1


# ---------- columns ----------

def guess_column(name: str) -> Column | None:
    lowered = name.lower()
    for column, words in HEADER_WORDS.items():
        if any(w in lowered for w in words):
            return column
    return None


def find_table(rows: list[list[str]]) -> Table:
    """The first row that names a date column and an amount (or in/out) column is the header."""
    for index, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        mapping: dict[Column, int | None] = {c: None for c in COLUMNS}
        for i, cell in enumerate(row):
            column = guess_column(cell)
            if column and mapping[column] is None:
                mapping[column] = i
        has_money = mapping["amount"] is not None or mapping["income"] is not None or mapping["expense"] is not None
        if mapping["date"] is not None and has_money:
            return Table(rows=rows, header_row=index, mapping=mapping)
    raise ImportError_("import.error.no_header")


# ---------- values ----------

DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y.%m.%d", "%Y/%m/%d", "%d.%m.%y")
EXCEL_EPOCH = date(1899, 12, 30)


def parse_date(text: str) -> date | None:
    text = text.strip()
    if not text:
        return None
    if re.fullmatch(r"\d{5}(\.\d+)?", text):  # Excel serial date
        return EXCEL_EPOCH + timedelta(days=int(float(text)))
    head = re.split(r"[ T]", text)[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(head, fmt).date()
        except ValueError:
            continue
    return None


def parse_money(text: str) -> Decimal | None:
    """'1 234,56' / '1,234.56' / '-1234.5' / '(250.00)' / '1.234,56 GEL' -> Decimal; None if not a number."""
    cleaned = re.sub(r"[^\d,.\-()]", "", text.replace("−", "-"))
    if not re.search(r"\d", cleaned):
        return None
    negative = cleaned.startswith("-") or cleaned.endswith("-") or (cleaned.startswith("(") and cleaned.endswith(")"))
    digits = cleaned.strip("-()")
    last = max(digits.rfind(","), digits.rfind("."))
    if last >= 0:
        # The last separator is the decimal point when both kinds appear, or when a lone one isn't followed by
        # exactly three digits (money never has three decimals, so "1,234" / "1.234" group thousands).
        both = "," in digits and "." in digits
        lone = digits.count(digits[last]) == 1 and len(digits) - last - 1 != 3
        whole, fraction = re.sub(r"[,.]", "", digits[:last]), digits[last + 1:]
        digits = f"{whole}.{fraction}" if both or lone else whole + fraction
    try:
        value = Decimal(digits)
    except InvalidOperation:
        return None
    return -value if negative else value


def fingerprint(key: tuple, occurrence: int) -> str:
    """Same row, same position among identical rows -> same id, so a re-import is recognised."""
    return hashlib.sha256(f"{key}|{occurrence}".encode()).hexdigest()


def parse_table(table: Table, mapping: dict[Column, int | None] | None = None) -> tuple[list[ParsedRow], list[SkippedRow]]:
    mapping = mapping or table.mapping
    cell = lambda row, column: row[mapping[column]].strip() if mapping.get(column) is not None and mapping[column] < len(row) else ""
    parsed, skipped = [], []
    seen: Counter = Counter()
    for index in range(table.header_row + 1, min(len(table.rows), table.header_row + 1 + MAX_ROWS)):
        row, number = table.rows[index], index + 1
        occurred_on = parse_date(cell(row, "date"))
        if occurred_on is None:
            if any(row):
                skipped.append(SkippedRow(row=number, reason="no_date"))
            continue
        income, expense = parse_money(cell(row, "income")), parse_money(cell(row, "expense"))
        signed = parse_money(cell(row, "amount"))
        if income:
            direction, amount = TransactionDirection.income, abs(income)
        elif expense:
            direction, amount = TransactionDirection.expense, abs(expense)
        elif signed is not None:
            direction = TransactionDirection.income if signed > 0 else TransactionDirection.expense
            amount = abs(signed)
        else:
            skipped.append(SkippedRow(row=number, reason="no_amount"))
            continue
        if amount == 0:
            skipped.append(SkippedRow(row=number, reason="zero"))
            continue
        description = cell(row, "description")[:1000] or None
        counterparty = cell(row, "counterparty")[:255] or None
        key = (occurred_on.isoformat(), direction.value, str(amount.quantize(Decimal("0.01"))), description, counterparty)
        seen[key] += 1
        parsed.append(ParsedRow(row=number, occurred_on=occurred_on, direction=direction,
                                amount=amount.quantize(Decimal("0.01")), description=description,
                                counterparty=counterparty, external_id=fingerprint(key, seen[key])))
    return parsed, skipped
