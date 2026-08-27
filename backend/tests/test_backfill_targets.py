"""Target selection for backfill_room_type_and_rate_plan.

The two passes decide which rows the per-reservation backfill spends its
per-tick budget on. Pass B's check_in guard is the fix for a feedback loop:
future-dated bookings have no accommodation revenue yet, so they re-qualified
on every tick forever and — because each fetch rewrote room_type and bumped
updated_at — kept crowding out the rows that had no room_type at all.
"""
from datetime import date

from app.services.cloudbeds import (
    missing_revenue_filter,
    missing_room_type_filter,
)


def _sql(clause):
    return str(clause.compile(compile_kwargs={"literal_binds": True})).lower()


class TestMissingRoomType:
    def test_selects_rows_with_no_room_type(self):
        sql = _sql(missing_room_type_filter())
        assert "reservations.room_type is null" in sql

    def test_does_not_look_at_revenue_or_status(self):
        # Pass A must not inherit pass B's conditions — a cancelled booking
        # with no room_type is still unmatchable and still needs filling.
        sql = _sql(missing_room_type_filter())
        assert "grand_total" not in sql
        assert "status" not in sql


class TestMissingRevenue:
    def test_requires_stay_to_have_started(self):
        sql = _sql(missing_revenue_filter(date(2026, 8, 27)))
        assert "reservations.check_in_date <= '2026-08-27'" in sql

    def test_only_rows_that_already_have_a_room_type(self):
        sql = _sql(missing_revenue_filter(date(2026, 8, 27)))
        assert "reservations.room_type is not null" in sql

    def test_excludes_cancelled_and_no_show(self):
        sql = _sql(missing_revenue_filter(date(2026, 8, 27)))
        assert "not in" in sql
        assert "canceled" in sql
        assert "no_show" in sql

    def test_matches_null_or_zero_revenue(self):
        sql = _sql(missing_revenue_filter(date(2026, 8, 27)))
        assert "grand_total_native is null" in sql
        assert "grand_total_native = 0" in sql

    def test_conditions_are_anded(self):
        # An OR here would drag every future booking back in and restore the
        # loop this guard exists to break.
        sql = _sql(missing_revenue_filter(date(2026, 8, 27)))
        assert " or " in sql          # only inside the null/zero pair
        assert sql.count(" and ") >= 3
