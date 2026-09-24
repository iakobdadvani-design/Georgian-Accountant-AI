import json
from collections import defaultdict
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter

from app.rules.schema import TaxRule

DATA_DIR = Path(__file__).parent / "data"

_rule_list = TypeAdapter(list[TaxRule])


class RuleSetError(ValueError):
    pass


def validate_rule_set(rules: list[TaxRule]) -> None:
    """Reject duplicate versions and overlapping effective ranges, so at most one version applies per day."""
    by_id: dict[str, list[TaxRule]] = defaultdict(list)
    for rule in rules:
        if rule.effective_to is not None and rule.effective_to < rule.effective_from:
            raise RuleSetError(f"{rule.rule_id} v{rule.version}: effective_to is before effective_from")
        by_id[rule.rule_id].append(rule)

    for rule_id, versions in by_id.items():
        if len({r.version for r in versions}) != len(versions):
            raise RuleSetError(f"{rule_id}: duplicate version numbers")
        versions.sort(key=lambda r: r.effective_from)
        for earlier, later in zip(versions, versions[1:]):
            if (earlier.effective_to or date.max) >= later.effective_from:
                raise RuleSetError(f"{rule_id}: v{earlier.version} and v{later.version} have overlapping dates")


def load_rules(data_dir: Path = DATA_DIR) -> list[TaxRule]:
    rules: list[TaxRule] = []
    for path in sorted(data_dir.glob("*.json")):
        rules.extend(_rule_list.validate_python(json.loads(path.read_text(encoding="utf-8"))))
    validate_rule_set(rules)
    return rules


@lru_cache
def get_rules() -> list[TaxRule]:
    return load_rules()
