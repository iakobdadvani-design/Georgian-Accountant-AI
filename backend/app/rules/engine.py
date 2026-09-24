"""Deterministic rule evaluation. No I/O, no AI: same rules + facts + date always give the same result."""

import operator
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.rules.schema import (
    AllOf,
    AnyOf,
    Compare,
    Condition,
    FactValue,
    Fixed,
    LocalizedText,
    Percentage,
    RuleResult,
    TaxRule,
)

Facts = dict[str, FactValue]

CENT = Decimal("0.01")

OPS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
}
OP_SYMBOLS = {"eq": "==", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}


def as_decimal(value: FactValue) -> Decimal | None:
    """Numeric view of a fact; None for booleans and non-numeric strings. Floats go via str to avoid binary noise."""
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def check(
    condition: Condition, facts: Facts, missing: list[str], trace: list[str], reasons: list[LocalizedText]
) -> bool | None:
    """Tri-state: True / False, or None when a needed fact is missing.

    Collects the `if_false` explanation of every condition that evaluated False.
    """
    if isinstance(condition, AllOf):
        results = [check(c, facts, missing, trace, reasons) for c in condition.all]
        return False if False in results else None if None in results else True
    if isinstance(condition, AnyOf):
        results = [check(c, facts, missing, trace, reasons) for c in condition.any]
        return True if True in results else None if None in results else False

    assert isinstance(condition, Compare)
    symbol = OP_SYMBOLS[condition.op]
    if condition.fact not in facts:
        missing.append(condition.fact)
        trace.append(f"{condition.fact} {symbol} {condition.value!r}: fact missing")
        return None

    actual = facts[condition.fact]
    left, right = as_decimal(actual), as_decimal(condition.value)
    if isinstance(actual, bool) != isinstance(condition.value, bool):
        outcome = condition.op == "ne"  # a boolean never equals a number or string
    elif left is not None and right is not None:
        outcome = OPS[condition.op](left, right)
    elif condition.op in ("eq", "ne"):
        outcome = OPS[condition.op](actual, condition.value)
    else:
        outcome = False
    trace.append(f"{condition.fact} ({actual!r}) {symbol} {condition.value!r}: {outcome}")
    if not outcome and condition.if_false is not None:
        reasons.append(condition.if_false)
    return outcome


def referenced_facts(rule: TaxRule) -> set[str]:
    """Every fact a rule reads, in its conditions or its calculation."""
    found: set[str] = set()

    def walk(condition: Condition) -> None:
        if isinstance(condition, AllOf):
            for c in condition.all:
                walk(c)
        elif isinstance(condition, AnyOf):
            for c in condition.any:
                walk(c)
        else:
            found.add(condition.fact)

    walk(rule.conditions)
    if isinstance(rule.calculation, Percentage):
        found.add(rule.calculation.base)
    return found


def evaluate_rule(rule: TaxRule, facts: Facts) -> RuleResult:
    missing: list[str] = []
    trace: list[str] = []
    result = RuleResult(
        rule_id=rule.rule_id,
        version=rule.version,
        title=rule.title,
        tax_type=rule.tax_type,
        status="not_applicable",
        legal_source=rule.legal_source,
        is_demo=rule.is_demo,
        verification=rule.verification,
        last_verified_date=rule.last_verified_date,
    )

    reasons: list[LocalizedText] = []
    matched = check(rule.conditions, facts, missing, trace, reasons)
    if matched is None:
        return result.model_copy(update={"status": "insufficient_data", "missing_facts": missing, "trace": trace})
    if not matched:
        return result.model_copy(update={"trace": trace, "reasons": reasons})

    amount = None
    if isinstance(rule.calculation, Percentage):
        base = as_decimal(facts[rule.calculation.base]) if rule.calculation.base in facts else None
        if base is None:
            trace.append(f"calculation base {rule.calculation.base} missing or not numeric")
            return result.model_copy(
                update={"status": "insufficient_data", "missing_facts": [rule.calculation.base], "trace": trace}
            )
        amount = (base * rule.calculation.rate).quantize(CENT, rounding=ROUND_HALF_UP)
        trace.append(f"{rule.calculation.base} ({base}) x {rule.calculation.rate} = {amount}")
    elif isinstance(rule.calculation, Fixed):
        amount = rule.calculation.amount.quantize(CENT, rounding=ROUND_HALF_UP)
        trace.append(f"fixed amount {amount}")

    return result.model_copy(update={"status": "applies", "amount": amount, "message": rule.message, "trace": trace})


def evaluate(rules: list[TaxRule], facts: Facts, as_of: date) -> list[RuleResult]:
    """Evaluate every rule version effective on `as_of`, in rule_id order."""
    active = sorted((r for r in rules if r.is_effective_on(as_of)), key=lambda r: r.rule_id)
    return [evaluate_rule(rule, facts) for rule in active]
