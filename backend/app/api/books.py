"""Sales and expenses: monthly figures, legal limits, and bank statement import.

Totals are sums of the company's own records; every tax answer is a rule evaluated with those sums as facts.
"""

import base64
import binascii
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.companies import get_company
from app.books import (
    Alert, Totals, alert, last_12_months, month_end, month_start, rule_threshold, taxable_turnover, totals,
    vat_inside,
)
from app.books.importer import COLUMNS, Column, ImportError_, ParsedRow, SkippedRow, find_table, parse_table, read_rows
from app.database import get_db
from app.facts import company_facts
from app.models import Company, Transaction
from app.models.enums import TransactionDirection
from app.rules.engine import evaluate
from app.rules.loader import get_rules
from app.rules.schema import RuleResult

router = APIRouter(prefix="/companies/{company_id}/books", tags=["books"])

MAX_FILE_BYTES = 5 * 1024 * 1024
PREVIEW_ROWS = 15


class TotalsRead(BaseModel):
    income: Decimal
    expense: Decimal
    output_vat: Decimal
    input_vat: Decimal
    count: int


class LimitStatus(BaseModel):
    amount: Decimal
    limit: Decimal | None
    alert: Alert
    start: date
    end: date


class BooksSummary(BaseModel):
    month: date
    totals: TotalsRead
    turnover_12m: LimitStatus = Field(description="VAT-taxable sales (without VAT) over the 12 months ending this month")
    vat_registration: RuleResult | None = Field(description="Only for companies that aren't VAT-registered")
    vat_payable: RuleResult | None = Field(description="Only for VAT payers: this month's output minus input VAT")
    year_income: LimitStatus | None = Field(description="Only for small businesses: gross income this year so far")
    small_business_tax: RuleResult | None


def rule(rule_id: str):
    return next(r for r in get_rules() if r.rule_id == rule_id)


def run(rule_id: str, facts: dict, as_of: date) -> RuleResult | None:
    """The rule's result on as_of, or None if no version is in effect then."""
    return next(iter(evaluate([r for r in get_rules() if r.rule_id == rule_id], facts, as_of)), None)


def summary(company: Company, db: Session, month: date) -> BooksSummary:
    start, end = month_start(month), month_end(month)
    records = db.scalars(select(Transaction).where(Transaction.company_id == company.id)).all()
    facts = company_facts(company, db)
    month_totals: Totals = totals(records, start, end)

    window_start, window_end = last_12_months(month)
    turnover = taxable_turnover(records, window_start, window_end)
    registered = facts.get("company.vat_registered")
    vat_registration = vat_payable = None
    if registered is False:
        vat_registration = run("ge.vat.registration_threshold", {**facts, "input.taxable_turnover_12m": str(turnover)}, end)
    if registered:
        vat_payable = run("ge.vat.payable", {**facts, "input.output_vat": str(month_totals.output_vat),
                                             "input.input_vat": str(month_totals.input_vat)}, end)
    vat_limit = rule_threshold(rule("ge.vat.registration_threshold"), "input.taxable_turnover_12m")
    turnover_status = LimitStatus(
        amount=turnover, limit=vat_limit, start=window_start, end=window_end,
        alert="none" if registered is not False else alert(
            turnover, vat_limit, vat_registration is not None and vat_registration.status == "applies"))

    year_income = small_business_tax = None
    if facts.get("company.tax_regime") == "small_business":
        sb_rule = rule("ge.small_business.tax")
        limit = sb_rule.limits.get("year_gross_income")
        so_far = totals(records, date(month.year, 1, 1), end).income
        over = limit is not None and so_far > limit
        year_income = LimitStatus(amount=so_far, limit=limit, alert=alert(so_far, limit, over),
                                  start=date(month.year, 1, 1), end=end)
        small_business_tax = run("ge.small_business.tax", {**facts, "input.small_business_income": str(month_totals.income),
                                                           "input.over_small_business_limit": over}, end)

    return BooksSummary(month=start, totals=TotalsRead(**month_totals.__dict__), turnover_12m=turnover_status,
                        vat_registration=vat_registration, vat_payable=vat_payable, year_income=year_income,
                        small_business_tax=small_business_tax)


@router.get("", response_model=BooksSummary)
def books_summary(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM; default: as_of's month"),
    as_of: date = Query(default_factory=date.today),
    company: Company = Depends(get_company),
    db: Session = Depends(get_db),
):
    chosen = date(int(month[:4]), int(month[5:]), 1) if month else as_of
    return summary(company, db, chosen)


# ---------- import ----------

class ImportFile(BaseModel):
    filename: str = Field(max_length=255)
    content: str = Field(description="The file, base64-encoded")
    mapping: dict[Column, int | None] | None = Field(default=None, description="Column index per field; default: guessed")


class ImportRequest(ImportFile):
    sales_include_vat: bool = Field(default=False, description="Record the 18% VAT inside each sale (VAT payers)")
    purchases_include_vat: bool = Field(default=False, description="Record the 18% VAT inside each purchase")


class ImportPreview(BaseModel):
    header: list[str]
    mapping: dict[Column, int | None]
    rows: list[ParsedRow]
    total: int
    income: int
    expense: int
    duplicates: int
    skipped: list[SkippedRow]


class ImportResult(BaseModel):
    imported: int
    duplicates: int
    skipped: list[SkippedRow]


def parse_upload(payload: ImportFile) -> tuple[list[str], dict, list[ParsedRow], list[SkippedRow]]:
    try:
        content = base64.b64decode(payload.content, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "import.error.unreadable")
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "import.error.too_large")
    try:
        table = find_table(read_rows(payload.filename, content))
    except ImportError_ as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    mapping = {c: (payload.mapping or table.mapping).get(c) for c in COLUMNS}
    if mapping["date"] is None or all(mapping[c] is None for c in ("amount", "income", "expense")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "import.error.mapping")
    rows, skipped = parse_table(table, mapping)
    return table.header, mapping, rows, skipped


def existing_ids(company: Company, db: Session, rows: list[ParsedRow]) -> set[str]:
    ids = [r.external_id for r in rows]
    found: set[str] = set()
    for i in range(0, len(ids), 500):
        found.update(db.scalars(select(Transaction.external_id).where(
            Transaction.company_id == company.id, Transaction.external_id.in_(ids[i:i + 500]))))
    return found


@router.post("/import/preview", response_model=ImportPreview)
def preview_import(payload: ImportFile, company: Company = Depends(get_company), db: Session = Depends(get_db)):
    header, mapping, rows, skipped = parse_upload(payload)
    return ImportPreview(header=header, mapping=mapping, rows=rows[:PREVIEW_ROWS], total=len(rows),
                         income=sum(r.direction == TransactionDirection.income for r in rows),
                         expense=sum(r.direction == TransactionDirection.expense for r in rows),
                         duplicates=len(existing_ids(company, db, rows)), skipped=skipped)


@router.post("/import", response_model=ImportResult)
def run_import(payload: ImportRequest, company: Company = Depends(get_company), db: Session = Depends(get_db)):
    _, _, rows, skipped = parse_upload(payload)
    already = existing_ids(company, db, rows)
    facts = company_facts(company, db)
    new = [r for r in rows if r.external_id not in already]
    for r in new:
        is_sale = r.direction == TransactionDirection.income
        with_vat = payload.sales_include_vat if is_sale else payload.purchases_include_vat
        db.add(Transaction(
            company_id=company.id, occurred_on=r.occurred_on, direction=r.direction, amount=r.amount,
            vat_amount=vat_inside(r.amount, facts, r.occurred_on) if with_vat else None,
            category="sales" if is_sale else "purchase", counterparty=r.counterparty, description=r.description,
            external_id=r.external_id))
    db.commit()
    return ImportResult(imported=len(new), duplicates=len(rows) - len(new), skipped=skipped)
