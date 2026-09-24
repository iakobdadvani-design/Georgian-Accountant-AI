from datetime import date
from decimal import Decimal

import pytest

from app.rules.engine import evaluate, evaluate_rule
from app.rules.loader import RuleSetError, load_rules, validate_rule_set
from app.rules.schema import TaxRule

SOURCE = {"citation": "test"}


def rule(**overrides) -> TaxRule:
    return TaxRule.model_validate({
        "rule_id": "t.rule",
        "version": 1,
        "title": "test",
        "tax_type": "test",
        "effective_from": "2020-01-01",
        "conditions": {"fact": "input.x", "op": "gt", "value": 100},
        "legal_source": SOURCE,
        **overrides,
    })


def by_id(results):
    return {(r["rule_id"] if isinstance(r, dict) else r.rule_id): r for r in results}


# --- conditions ---

@pytest.mark.parametrize("value, expected", [(101, "applies"), (100, "not_applicable"), ("150.5", "applies")])
def test_compare_threshold(value, expected):
    assert evaluate_rule(rule(), {"input.x": value}).status == expected


def test_missing_fact_is_insufficient_data_not_false():
    result = evaluate_rule(rule(), {})
    assert result.status == "insufficient_data"
    assert result.missing_facts == ["input.x"]


def test_all_of_short_circuits_to_false_even_with_missing_fact():
    r = rule(conditions={"all": [{"fact": "a", "op": "eq", "value": True}, {"fact": "b", "op": "gt", "value": 1}]})
    assert evaluate_rule(r, {"a": False}).status == "not_applicable"
    assert evaluate_rule(r, {"a": True}).status == "insufficient_data"
    assert evaluate_rule(r, {"a": True, "b": 2}).status == "applies"


def test_any_of():
    r = rule(conditions={"any": [{"fact": "a", "op": "eq", "value": "x"}, {"fact": "b", "op": "lt", "value": 0}]})
    assert evaluate_rule(r, {"b": -1}).status == "applies"
    assert evaluate_rule(r, {"a": "y", "b": 1}).status == "not_applicable"
    assert evaluate_rule(r, {"a": "y"}).status == "insufficient_data"


def test_bool_is_not_treated_as_number():
    r = rule(conditions={"fact": "flag", "op": "eq", "value": 1})
    assert evaluate_rule(r, {"flag": True}).status == "not_applicable"


# --- calculations ---

def test_percentage_uses_exact_decimal_and_half_up_rounding():
    r = rule(conditions={"fact": "s", "op": "gt", "value": 0},
             calculation={"type": "percentage", "base": "s", "rate": "0.1"})
    assert evaluate_rule(r, {"s": "0.05"}).amount == Decimal("0.01")  # 0.005 rounds up
    assert evaluate_rule(r, {"s": 0.1 + 0.2}).amount == Decimal("0.03")
    assert evaluate_rule(r, {"s": "2500.50"}).amount == Decimal("250.05")


def test_percentage_missing_base_is_insufficient_data():
    r = rule(conditions={"fact": "a", "op": "eq", "value": True},
             calculation={"type": "percentage", "base": "s", "rate": "0.1"})
    result = evaluate_rule(r, {"a": True})
    assert result.status == "insufficient_data"
    assert result.missing_facts == ["s"]


def test_result_has_trace():
    result = evaluate_rule(rule(calculation={"type": "fixed", "amount": "50"}), {"input.x": 150})
    assert result.amount == Decimal("50.00")
    assert any("input.x" in step for step in result.trace)


# --- versioning ---

def test_version_selected_by_date():
    rules = [
        rule(version=1, effective_to="2024-12-31", calculation={"type": "fixed", "amount": "1"}),
        rule(version=2, effective_from="2025-01-01", calculation={"type": "fixed", "amount": "2"}),
    ]
    facts = {"input.x": 500}
    assert [r.version for r in evaluate(rules, facts, date(2024, 12, 31))] == [1]
    assert [r.version for r in evaluate(rules, facts, date(2025, 1, 1))] == [2]
    assert evaluate(rules, facts, date(2019, 12, 31)) == []


def test_overlapping_versions_rejected():
    with pytest.raises(RuleSetError, match="overlapping"):
        validate_rule_set([rule(version=1), rule(version=2, effective_from="2023-01-01")])


def test_duplicate_versions_rejected():
    with pytest.raises(RuleSetError, match="duplicate"):
        validate_rule_set([rule(effective_to="2021-01-01"), rule(effective_from="2022-01-01")])


def test_unknown_operator_rejected():
    with pytest.raises(ValueError):
        rule(conditions={"fact": "x", "op": "contains", "value": 1})


def test_shipped_rule_files_are_valid():
    rules = load_rules()
    assert any(r.is_demo for r in rules)
    real = [r for r in rules if not r.is_demo]
    # Real rules must carry a legal source; none is verified until a professional signs off.
    assert real and all(r.legal_source.url and r.verification == "unverified" for r in real)


@pytest.mark.parametrize("turnover, registered, expected", [
    ("100000", False, "not_applicable"),  # must *exceed* GEL 100 000
    ("100000.01", False, "applies"),
    ("250000", True, "not_applicable"),
])
def test_vat_registration_threshold(turnover, registered, expected):
    facts = {"input.taxable_turnover_12m": turnover, "company.vat_registered": registered}
    [result] = [r for r in evaluate(load_rules(), facts, date(2025, 6, 1)) if r.rule_id == "ge.vat.registration_threshold"]
    assert result.status == expected
    assert result.legal_source.citation["en"] == "Tax Code of Georgia, Article 165(1)"


# --- API ---

def test_evaluate_endpoint_uses_demo_rules(client):
    response = client.post("/rules/evaluate", json={"as_of": "2025-06-01", "facts": {"input.gross_salary": "2500"}})
    assert response.status_code == 200
    payroll = by_id(response.json())["demo.payroll_withholding"]
    assert payroll["version"] == 2
    assert Decimal(payroll["amount"]) == Decimal("300.00")


def test_company_evaluate_pulls_facts_from_db(client):
    company = client.post("/companies", json={
        "name": "Rules LLC", "tax_id": "404111111", "legal_form": "LLC", "registration_date": "2024-01-01",
    }).json()
    url = f"/companies/{company['id']}/evaluate"
    body = {"as_of": "2025-06-01", "inputs": {"taxable_turnover_12m": "150000"}}

    before = by_id(client.post(url, json=body).json())
    assert before["ge.vat.registration_threshold"]["status"] == "insufficient_data"
    assert before["ge.vat.registration_threshold"]["missing_facts"] == ["company.vat_registered"]

    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": True})
    after = by_id(client.post(url, json=body).json())
    assert after["ge.vat.registration_threshold"]["status"] == "not_applicable"
    assert after["demo.registered_flat_fee"]["status"] == "applies"
