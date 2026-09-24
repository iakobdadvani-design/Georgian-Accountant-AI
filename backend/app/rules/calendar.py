"""Upcoming filing/payment dates for a company. Deterministic: deadlines file + company facts + today's date."""

import calendar as cal
import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from app.rules.engine import Facts, check
from app.rules.schema import Annual, Deadline, Monthly

DEADLINES_FILE = Path(__file__).parent / "deadlines.json"

# Keep the most recent missed period visible until it's marked done, without greeting a new user with a
# backlog of every past month.
LOOKBACK_DAYS = 31


class Occurrence(BaseModel):
    deadline: Deadline
    period_start: date
    period_end: date
    due_date: date

    @property
    def key(self) -> str:
        return f"{self.deadline.deadline_id}:{self.period_start.isoformat()}"


def load_deadlines(path: Path = DEADLINES_FILE) -> list[Deadline]:
    deadlines = TypeAdapter(list[Deadline]).validate_python(json.loads(path.read_text(encoding="utf-8")))
    ids = [d.deadline_id for d in deadlines]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate deadline_id in deadlines file")
    return deadlines


@lru_cache
def get_deadlines() -> list[Deadline]:
    return load_deadlines()


def _month_start(d: date, offset: int = 0) -> date:
    index = d.year * 12 + d.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def _month_end(d: date) -> date:
    return d.replace(day=cal.monthrange(d.year, d.month)[1])


def _occurrences(deadline: Deadline, start: date, end: date) -> list[Occurrence]:
    found = []
    schedule = deadline.schedule
    if isinstance(schedule, Monthly):
        # Period P is due on `day` of the month after P.
        period = _month_start(start, -2)
        while True:
            due = _month_start(period, 1).replace(day=schedule.day)
            if due > end:
                break
            if due >= start:
                found.append(Occurrence(deadline=deadline, period_start=period, period_end=_month_end(period), due_date=due))
            period = _month_start(period, 1)
    elif isinstance(schedule, Annual):
        for year in range(start.year, end.year + 1):
            due = date(year, schedule.month, schedule.day)
            if start <= due <= end:
                period_year = year - 1 if schedule.period == "previous_year" else year
                found.append(Occurrence(deadline=deadline, period_start=date(period_year, 1, 1),
                                        period_end=date(period_year, 12, 31), due_date=due))
    return found


def upcoming(facts: Facts, today: date, months: int = 3, deadlines: list[Deadline] | None = None) -> list[Occurrence]:
    """Occurrences of every applicable deadline due between LOOKBACK_DAYS ago and `months` ahead, by due date."""
    start, end = today - timedelta(days=LOOKBACK_DAYS), _month_end(_month_start(today, months))
    result = []
    for deadline in deadlines if deadlines is not None else get_deadlines():
        if check(deadline.applies, facts, [], [], []):  # a missing fact (None) means "don't show"
            result.extend(_occurrences(deadline, start, end))
    return sorted(result, key=lambda o: (o.due_date, o.deadline.deadline_id))
