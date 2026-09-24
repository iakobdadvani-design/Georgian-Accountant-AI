"""The company's own records of sales and expenses, and what the rules engine makes of them.

Here we only add up recorded amounts. Every tax answer (register for VAT? how much VAT or small business tax?)
comes from evaluating a rule with those sums as facts, exactly as if the user had typed them in the chat.
"""

import calendar as cal
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Literal

from app.models import Transaction
from app.models.enums import TransactionDirection
from app.rules.engine import evaluate
from app.rules.loader import get_rules
from app.rules.schema import Compare, TaxRule

ZERO = Decimal("0.00")
# Warn once recorded sales reach this share of a legal limit. A product choice, not law.
APPROACHING_SHARE = Decimal("0.8")

Alert = Literal["none", "approaching", "exceeded"]


def month_start(d: date, offset: int = 0) -> date:
    index = d.year * 12 + d.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def month_end(d: date) -> date:
    return d.replace(day=cal.monthrange(d.year, d.month)[1])


@dataclass(frozen=True)
class Totals:
    income: Decimal = ZERO
    expense: Decimal = ZERO
    output_vat: Decimal = ZERO  # VAT inside recorded sales
    input_vat: Decimal = ZERO  # VAT inside recorded purchases
    count: int = 0


def totals(transactions: Iterable[Transaction], start: date, end: date) -> Totals:
    """Sums of GEL transactions dated start..end (inclusive). Other currencies aren't converted, so they're left out."""
    income = expense = output_vat = input_vat = ZERO
    count = 0
    for t in transactions:
        if not (start <= t.occurred_on <= end) or t.currency != "GEL":
            continue
        count += 1
        vat = t.vat_amount or ZERO
        if t.direction == TransactionDirection.income:
            income += t.amount
            output_vat += vat
        else:
            expense += t.amount
            input_vat += vat
    return Totals(income, expense, output_vat, input_vat, count)


def last_12_months(as_of: date) -> tuple[date, date]:
    """The 12 calendar months ending with as_of's month (Tax Code Art. 165(1) counts 12 consecutive months)."""
    return month_start(as_of, -11), month_end(as_of)


def taxable_turnover(transactions: Iterable[Transaction], start: date, end: date) -> Decimal:
    """Recorded sales without the VAT charged on them: the VAT-taxable turnover for the registration threshold."""
    t = totals(transactions, start, end)
    return t.income - t.output_vat


def rule_threshold(rule: TaxRule, fact: str) -> Decimal | None:
    """The value a rule compares `fact` against (e.g. 100 000 for the VAT registration turnover)."""
    stack = [rule.conditions]
    while stack:
        condition = stack.pop()
        if isinstance(condition, Compare):
            if condition.fact == fact:
                return Decimal(str(condition.value))
        else:
            stack.extend(getattr(condition, "all", None) or getattr(condition, "any", None) or [])
    return None


def alert(amount: Decimal, limit: Decimal | None, exceeded: bool) -> Alert:
    if limit is None:
        return "none"
    if exceeded:
        return "exceeded"
    return "approaching" if amount >= limit * APPROACHING_SHARE else "none"


def vat_inside(amount: Decimal, facts: dict, as_of: date) -> Decimal | None:
    """The VAT contained in a VAT-inclusive amount, from rule ge.vat.output_vat; None if it doesn't apply."""
    rules = [r for r in get_rules() if r.rule_id == "ge.vat.output_vat"]
    for result in evaluate(rules, {**facts, "input.sale_amount": str(amount), "input.vat_inclusive": True}, as_of):
        if result.status == "applies":
            return result.amount
    return None
