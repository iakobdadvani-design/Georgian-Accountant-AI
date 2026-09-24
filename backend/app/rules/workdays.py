"""Georgian working days, for moving deadlines that fall on a day off.

Tax Code Art. 3(2): a working day is any day except Saturday, Sunday and the holidays set by the Labour Code.
Art. 3(6): when the last day of a time limit is a non-working day, it runs to the end of the next working day.
Holidays: Labour Code Art. 30(1) (Matsne 1155567, consolidated version checked 2026-09-24). Days the Government
declares off ad hoc are not included. Needs accountant review.
"""

from datetime import date, timedelta
from functools import cache

# (month, day)
FIXED_HOLIDAYS = [
    (1, 1), (1, 2),  # New Year
    (1, 7),  # Christmas
    (1, 19),  # Epiphany
    (3, 3),  # Mother's Day
    (3, 8),  # International Women's Day
    (4, 9),  # National Unity Day
    (5, 9),  # Victory Day
    (5, 12),  # St Andrew the First-Called
    (5, 17),  # Family Purity and Respect for Parents Day
    (5, 26),  # Independence Day
    (8, 28),  # Assumption (Mariamoba)
    (10, 14),  # Svetitskhovloba
    (11, 23),  # St George's Day (Giorgoba)
]
# Good Friday, Holy Saturday, Easter Sunday, Easter Monday
EASTER_OFFSETS = (-2, -1, 0, 1)


def orthodox_easter(year: int) -> date:
    """Orthodox Easter Sunday in the Gregorian calendar (Meeus' Julian algorithm; valid 1900-2099)."""
    a, b, c = year % 4, year % 7, year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month, day = divmod(d + e + 114, 31)
    return date(year, month, day + 1) + timedelta(days=13)


@cache
def holidays(year: int) -> frozenset[date]:
    easter = orthodox_easter(year)
    return frozenset([date(year, m, d) for m, d in FIXED_HOLIDAYS]
                     + [easter + timedelta(days=n) for n in EASTER_OFFSETS])


def is_working_day(day: date) -> bool:
    return day.weekday() < 5 and day not in holidays(day.year)


def next_working_day(day: date) -> date:
    """`day` itself if it's a working day, otherwise the first working day after it."""
    while not is_working_day(day):
        day += timedelta(days=1)
    return day
