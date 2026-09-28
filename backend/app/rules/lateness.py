"""How late a payment or a return is, counted the way the penalty rules need it.

Only date arithmetic; the penalties themselves are rules (ge.penalty.late_payment, ge.penalty.late_filing).
"""

import calendar as cal
from dataclasses import dataclass
from datetime import date


def add_months(d: date, months: int) -> date:
    index = d.year * 12 + d.month - 1 + months
    year, month = index // 12, index % 12 + 1
    return date(year, month, min(d.day, cal.monthrange(year, month)[1]))


@dataclass(frozen=True)
class Lateness:
    days: int    # Art. 272(2), (4): from the day after the due date up to and including the day of payment
    months: int  # Art. 274(1): overdue months, an incomplete month counting as a whole one


def lateness(due: date, done_on: date) -> Lateness:
    """How late something due on `due` is when paid/filed on `done_on` (zero if on time)."""
    if done_on <= due:
        return Lateness(0, 0)
    months = 1
    while add_months(due, months) < done_on:
        months += 1
    return Lateness((done_on - due).days, months)
