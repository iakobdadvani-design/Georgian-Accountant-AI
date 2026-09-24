"""Deterministic rule evaluation. No I/O, no AI: same rules + facts + date always give the same result."""

import operator
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.rules.schema import (
    CONSTANT,
    AllOf,
    AnyOf,
    BreakdownLine,
    Compare,
    Condition,
    FactValue,
    Fixed,
    LocalizedText,
    Percentage,
    RuleResult,
    Steps,
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
    elif isinstance(rule.calculation, Steps):
        for step in rule.calculation.steps:
            found.update(arg for arg in step.args if "." in arg and not CONSTANT.match(arg))
            if step.when is not None:
                walk(step.when)
    return found


STEP_SYMBOLS = {"multiply": " x ", "divide": " / ", "subtract": " - ", "add": " + "}


def run_steps(calculation: Steps, facts: Facts, trace: list[str]) -> tuple[dict[str, Decimal], list[str]]:
    """Evaluate steps in order. Returns step values, or the facts that were missing or not numeric."""
    values: dict[str, Decimal] = {}
    for step in calculation.steps:
        if step.when is not None:
            missing: list[str] = []
            applies = check(step.when, facts, missing, trace, [])
            if applies is None:
                return values, missing
            if not applies:
                values[step.name] = Decimal("0.00")
                trace.append(f"{step.name} = 0 (condition not met)")
                continue

        operands: list[Decimal] = []
        shown: list[str] = []
        for arg in step.args:
            if CONSTANT.match(arg):
                value = Decimal(arg)
                shown.append(arg)
            elif arg in values:
                value = values[arg]
                shown.append(f"{arg} ({value})")
            else:
                value = as_decimal(facts[arg]) if arg in facts else None
                if value is None:
                    return values, [arg]
                shown.append(f"{arg} ({value})")
            operands.append(value)

        first, rest = operands[0], operands[1:]
        if step.op == "multiply":
            result = first
            for x in rest:
                result *= x
        elif step.op == "divide":
            if any(x == 0 for x in rest):
                trace.append(f"{step.name}: division by zero")
                return values, [a for a in step.args[1:] if not CONSTANT.match(a)]
            result = first
            for x in rest:
                result /= x
        elif step.op == "subtract":
            result = first - sum(rest)
        else:
            result = first + sum(rest)
        if step.round:
            result = result.quantize(CENT, rounding=ROUND_HALF_UP)
        values[step.name] = result
        trace.append(f"{step.name} = {STEP_SYMBOLS[step.op].join(shown)} = {result}")
    return values, []


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
    elif isinstance(rule.calculation, Steps):
        values, missing_inputs = run_steps(rule.calculation, facts, trace)
        if missing_inputs:
            return result.model_copy(
                update={"status": "insufficient_data", "missing_facts": missing_inputs, "trace": trace})
        amount = values[rule.calculation.result]
        breakdown = [BreakdownLine(name=s.name, label=s.label, amount=values[s.name])
                     for s in rule.calculation.steps if s.show]
        label = next(s.label for s in rule.calculation.steps if s.name == rule.calculation.result)
        return result.model_copy(update={"status": "applies", "amount": amount, "amount_label": label,
                                         "breakdown": breakdown,
                                         "message": rule.message, "trace": trace})

    return result.model_copy(update={"status": "applies", "amount": amount, "message": rule.message, "trace": trace})


def evaluate(rules: list[TaxRule], facts: Facts, as_of: date) -> list[RuleResult]:
    """Evaluate every rule version effective on `as_of`, in rule_id order."""
    active = sorted((r for r in rules if r.is_effective_on(as_of)), key=lambda r: r.rule_id)
    return [evaluate_rule(rule, facts) for rule in active]
