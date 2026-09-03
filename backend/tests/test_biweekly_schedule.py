"""When the automatic Bi-Weekly send fires, and when it must not.

The job ticks every 15 minutes and emails branch managers, so the failure
modes are asymmetric: sending twice is noise in somebody's inbox, sending a
half-finished period is a wrong report, and never sending is a report nobody
notices is missing. These pin all three.

The arithmetic lives in `biweekly_schedule` as pure functions precisely so it
can be tested without a database, a mailbox, or a clock that has to be waited
on.
"""
from datetime import datetime, timedelta

import pytest

from app.services.biweekly_schedule import (
    DEFAULT_SEND_DAY_H1,
    DEFAULT_SEND_DAY_H2,
    due_period,
    is_due,
    next_send_at,
    period_due_on,
)
from app.services.report_common import ICT_TZ

H1, H2 = DEFAULT_SEND_DAY_H1, DEFAULT_SEND_DAY_H2   # 15th and the 1st


def ict(y, m, d, hh=9, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=ICT_TZ)


class _Sched:
    """The three columns `is_due` reads, without the ORM."""

    def __init__(self, day_h1=H1, day_h2=H2, hour=8, minute=0, last=None):
        self.send_day_h1 = day_h1
        self.send_day_h2 = day_h2
        self.hour = hour
        self.minute = minute
        self.last_sent_period_key = last


# ── Which period a given day owes ────────────────────────────────────────────


def test_the_15th_owes_the_first_half_of_that_month():
    p = period_due_on(ict(2026, 9, 15).date(), H1, H2)
    assert p is not None and p.key == "2026-09-H1"


def test_the_1st_owes_the_second_half_of_the_month_before():
    p = period_due_on(ict(2026, 9, 1).date(), H1, H2)
    assert p is not None and p.key == "2026-08-H2"


def test_the_1st_of_january_reaches_back_into_last_year():
    p = period_due_on(ict(2027, 1, 1).date(), H1, H2)
    assert p is not None and p.key == "2026-12-H2"


def test_an_ordinary_day_owes_nothing():
    assert period_due_on(ict(2026, 9, 9).date(), H1, H2) is None


@pytest.mark.parametrize("day_h1", range(15, 29))
def test_no_send_day_can_land_on_an_unfinished_period(day_h1):
    """The whole point of bounding the send days to 15–28 and 1–14.

    Whatever a person picks in the dialog, the period the day resolves to has
    already ended — so an automatic send can never mail a half-counted
    fortnight.
    """
    for month in range(1, 13):
        day = ict(2026, month, day_h1).date()
        p = period_due_on(day, day_h1, H2)
        assert p is not None
        assert p.end < day


# ── Catch-up, and not repeating ──────────────────────────────────────────────


def test_a_send_missed_by_an_outage_is_caught_up():
    """08:00 on the 15th is exactly when someone is deploying."""
    p = due_period(ict(2026, 9, 17), H1, H2)
    assert p is not None and p.key == "2026-09-H1"


def test_catch_up_stops_after_the_window():
    assert due_period(ict(2026, 9, 20), H1, H2) is None


def test_a_period_already_sent_is_not_sent_again():
    assert due_period(ict(2026, 9, 15), H1, H2,
                      last_sent_period_key="2026-09-H1") is None


def test_still_nothing_to_do_on_the_days_after_a_successful_send():
    for offset in range(0, 4):
        assert due_period(ict(2026, 9, 15) + timedelta(days=offset), H1, H2,
                          last_sent_period_key="2026-09-H1") is None


def test_the_next_period_is_still_owed_after_the_last_one_went_out():
    p = due_period(ict(2026, 10, 1), H1, H2, last_sent_period_key="2026-09-H1")
    assert p is not None and p.key == "2026-09-H2"


# ── The hour of the day ──────────────────────────────────────────────────────


def test_todays_send_waits_for_its_hour():
    assert is_due(ict(2026, 9, 15, 7, 59), _Sched(hour=8)) is None


def test_todays_send_goes_at_its_hour():
    p = is_due(ict(2026, 9, 15, 8, 0), _Sched(hour=8))
    assert p is not None and p.key == "2026-09-H1"


def test_a_catch_up_does_not_wait_for_the_hour_again():
    """Yesterday's 08:00 has passed. Holding it until tomorrow morning would
    make a late report later, not more punctual."""
    p = is_due(ict(2026, 9, 16, 0, 30), _Sched(hour=8))
    assert p is not None and p.key == "2026-09-H1"


def test_the_same_period_is_not_owed_twice_in_one_day():
    """Ticking every 15 minutes means this runs ~60 times on a send day."""
    sched = _Sched(hour=8)
    assert is_due(ict(2026, 9, 15, 8, 0), sched) is not None
    sched.last_sent_period_key = "2026-09-H1"
    for hh in range(8, 24):
        assert is_due(ict(2026, 9, 15, hh, 0), sched) is None
        assert is_due(ict(2026, 9, 15, hh, 45), sched) is None


# ── What the dialog prints ───────────────────────────────────────────────────


def test_next_run_skips_todays_hour_once_it_has_passed():
    assert next_send_at(ict(2026, 9, 15, 9, 0), H1, H2, 8, 0) == ict(2026, 10, 1, 8, 0)


def test_next_run_is_today_when_the_hour_is_still_ahead():
    assert next_send_at(ict(2026, 9, 15, 6, 0), H1, H2, 8, 0) == ict(2026, 9, 15, 8, 0)


def test_next_run_crosses_february_without_a_special_case():
    assert next_send_at(ict(2026, 2, 16), H1, H2, 8, 0) == ict(2026, 3, 1, 8, 0)
