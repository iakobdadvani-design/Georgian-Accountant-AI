"""Working days (Tax Code Art. 3(2), 3(6); Labour Code Art. 30) and deadlines moved off days off."""

from datetime import date

import pytest

from app.rules.calendar import upcoming
from app.rules.workdays import holidays, is_working_day, next_working_day, orthodox_easter


@pytest.mark.parametrize("year, easter", [
    (2024, date(2024, 5, 5)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 12)), (2027, date(2027, 5, 2)),
])
def test_orthodox_easter(year, easter):
    assert orthodox_easter(year) == easter


def test_easter_holidays_are_friday_to_monday():
    assert {date(2026, 4, 10), date(2026, 4, 11), date(2026, 4, 12), date(2026, 4, 13)} <= holidays(2026)


@pytest.mark.parametrize("day, working", [
    (date(2026, 9, 24), True),  # Thursday
    (date(2026, 9, 26), False),  # Saturday
    (date(2026, 11, 23), False),  # Giorgoba, a Monday
    (date(2026, 5, 26), False),  # Independence Day
])
def test_is_working_day(day, working):
    assert is_working_day(day) is working


def test_next_working_day_skips_weekend_and_holiday():
    # Sunday 15 March 2026 -> Monday 16th; Friday 1 January 2027 -> 1-2 Jan off, weekend, Mon 4th
    assert next_working_day(date(2026, 3, 15)) == date(2026, 3, 16)
    assert next_working_day(date(2027, 1, 1)) == date(2027, 1, 4)
    assert next_working_day(date(2026, 9, 24)) == date(2026, 9, 24)


def test_monthly_deadline_on_a_sunday_moves_to_monday():
    [o] = [o for o in upcoming({"company.vat_registered": True}, date(2026, 11, 1), months=1)
           if o.period_start == date(2026, 10, 1)]
    assert (o.statutory_date, o.due_date, o.shifted) == (date(2026, 11, 15), date(2026, 11, 16), True)


def test_annual_deadline_on_a_working_day_stays():
    [o] = upcoming({"company.tax_regime": "micro_business"}, date(2026, 1, 10), months=3)
    assert (o.statutory_date, o.due_date, o.shifted) == (date(2026, 3, 31), date(2026, 3, 31), False)


def test_api_and_chat_show_the_move(client):
    company = client.post("/companies", json={
        "name": "Shift LLC", "tax_id": "404555555", "legal_form": "LLC", "registration_date": "2024-01-01"}).json()
    client.put(f"/companies/{company['id']}/tax-profile", json={"vat_registered": True})
    items = client.get(f"/companies/{company['id']}/deadlines", params={"as_of": "2026-11-01", "months": 1}).json()
    vat = next(i for i in items if i["deadline_id"] == "ge.vat.monthly_return" and i["period_start"] == "2026-10-01")
    assert (vat["due_date"], vat["shifted_from"]) == ("2026-11-16", "2026-11-15")
    reply = client.post(f"/companies/{company['id']}/chat", json={"message": "what are my deadlines?",
                                                                   "as_of": "2026-11-01"}).json()["reply"]
    assert "by 16 November 2026 (moved from 15 November 2026, a day off)" in reply
