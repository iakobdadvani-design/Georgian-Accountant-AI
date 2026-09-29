"""Adding an employee from the chat ("I hired someone for 2 500 GEL on hand").

The chat only drafts the employee; the page shows the card and the user adds the name and personal number and presses
Save, which posts it to /employees. The gross salary on the card is the payroll rule's result, never computed here.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.chat.records import date_of, resolve_date
from app.rules.schema import RuleResult


class EmployeeDraft(BaseModel):
    gross_monthly_salary: Decimal
    net_monthly_salary: Decimal | None = None  # the take-home pay the user stated, when that's what they gave
    pension_participant: bool = True
    hired_on: date
    date_assumed: bool = False  # no start date given: as_of was used


def employee_draft(entities: dict, results: list[RuleResult], message: str, as_of: date) -> EmployeeDraft | None:
    if not entities.get("hire"):
        return None
    if "net_salary" in entities:
        result = next((r for r in results if r.rule_id == "ge.payroll.gross_from_net" and r.status == "applies"), None)
        if result is None:
            return None
        gross, net = result.amount, Decimal(str(entities["net_salary"]))
    elif "gross_salary" in entities:
        if not any(r.rule_id == "ge.payroll.income_tax" and r.status == "applies" for r in results):
            return None
        gross, net = Decimal(str(entities["gross_salary"])), None
    else:
        return None
    when, _ = date_of(message)
    return EmployeeDraft(gross_monthly_salary=gross, net_monthly_salary=net,
                         pension_participant=entities.get("pension_participant") is not False,
                         hired_on=resolve_date(when, as_of), date_assumed=when is None)
