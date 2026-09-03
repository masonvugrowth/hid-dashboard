"""Booking pace / pickup for future stay months.

Every occupancy figure HiD served before this read daily_metrics on the
check-in date basis: what already happened. Asked "of the bookings we took in
the last 60 days, how much of October, November and December is filled — and
how does that compare with the same stretch last year", the assistant had no
tool that crossed booking date with stay month, and said so.

What must not regress: nights are clipped to the stay month (a stay straddling
two months must not count whole in both), the denominator is that month's own
inventory, the group roll-up is summed on room-nights rather than averaged
across branches of different size, and the year-ago comparison is read at the
equivalent as-of date instead of against last year's finished occupancy.

The db is faked — the SQL is inspected, never executed. The arithmetic and the
window alignment are the whole of what these assert; neither needs Postgres.
"""
from datetime import date

import pytest

from app.services import chat_tools
from app.services.chat_tools import (
    TOOL_DEFS,
    TOOL_HANDLERS,
    _month_list,
    _pace_pct,
    _pace_pts,
    _parse_month,
    _shift_one_year,
    tool_get_booking_pace,
)


# ── Fake plumbing ───────────────────────────────────────────────────────────

class _FakeBranch:
    def __init__(self, bid, name, rooms, currency="TWD", room_count=None, dorm_count=None):
        self.id, self.name, self.total_rooms, self.currency = bid, name, rooms, currency
        self.total_room_count, self.total_dorm_count = room_count, dorm_count


class _FakeBranchQuery:
    def __init__(self, branches):
        self._branches = branches

    def filter_by(self, **kwargs):
        assert kwargs == {"is_active": True}
        return self

    def all(self):
        return self._branches


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeDB:
    """Hands back one canned row-set per execute() call, recording the SQL."""

    def __init__(self, snapshots, branches):
        self._snapshots = list(snapshots)
        self._branches = branches
        self.sql: list[str] = []
        self.params: list[dict] = []

    def execute(self, stmt, params):
        self.sql.append(str(stmt))
        self.params.append(params)
        return _FakeResult(self._snapshots.pop(0) if self._snapshots else [])

    def query(self, _model):
        return _FakeBranchQuery(self._branches)


def _row(bid, month, *, final, otb, pickup, otb_bookings=0, pickup_bookings=0,
         undated=0, otb_rev=0.0, pickup_rev=0.0):
    """One aggregate row in the column order _fetch_pace selects."""
    return (bid, month, final, otb, otb_bookings, undated, otb_rev,
            pickup, pickup_bookings, pickup_rev)


BID = "11111111-1111-1111-1111-111111111101"
Q4 = {"stay_month_from": "2026-10", "stay_month_to": "2026-10",
      "booked_from": "2026-06-27", "booked_to": "2026-08-25"}


# ── Pure helpers ────────────────────────────────────────────────────────────

def test_shift_one_year_keeps_the_calendar_day():
    # The year-ago booking window has to sit at the same distance from the stay
    # month, so it shifts by calendar day, not by 365 days.
    assert _shift_one_year(date(2026, 8, 25)) == date(2025, 8, 25)
    assert _shift_one_year(date(2026, 6, 27)) == date(2025, 6, 27)


def test_shift_one_year_survives_29_february():
    assert _shift_one_year(date(2024, 2, 29)) == date(2023, 2, 28)


def test_month_list_spans_the_year_boundary():
    assert _month_list((2026, 11), (2027, 1)) == [(2026, 11), (2026, 12), (2027, 1)]


def test_month_list_is_capped_and_order_insensitive():
    assert len(_month_list((2026, 1), (2030, 1))) == 12
    assert _month_list((2026, 12), (2026, 10)) == [(2026, 10), (2026, 11), (2026, 12)]


def test_parse_month_falls_back_on_junk():
    assert _parse_month("2026-10", (2026, 1)) == (2026, 10)
    assert _parse_month("2026-10-05", (2026, 1)) == (2026, 10)
    assert _parse_month("Q4", (2026, 1)) == (2026, 1)
    assert _parse_month("2026-13", (2026, 1)) == (2026, 1)
    assert _parse_month(None, (2026, 1)) == (2026, 1)


def test_pace_pct_and_pts_never_divide_by_zero():
    assert _pace_pct(620, 3100) == 20.0
    assert _pace_pct(5, 0) is None
    # Percentage POINTS between two rates, not a growth percentage.
    assert _pace_pts(620, 3100, 465, 3100) == 5.0
    assert _pace_pts(620, 3100, 465, 0) is None


# ── The tool ────────────────────────────────────────────────────────────────

def test_pickup_and_otb_are_read_against_that_months_inventory():
    branch = _FakeBranch(BID, "MEANDER Taipei", 100)
    db = _FakeDB(
        [
            [_row(BID, "2026-10", final=1550, otb=1550, pickup=620,
                  otb_bookings=700, pickup_bookings=300, pickup_rev=1_240_000.0)],
            [_row(BID, "2025-10", final=2480, otb=1240, pickup=465)],
        ],
        [branch],
    )
    out = tool_get_booking_pace(db, dict(Q4), None)
    r = out["rows"][0]

    # 100 rooms × 31 days in October.
    assert r["available_room_nights"] == 3100
    assert r["otb_occ_pct"] == 50.0
    assert r["pickup_occ_pct"] == 20.0
    # 620 of the 1550 nights on the books were booked inside the window.
    assert r["pickup_share_of_otb_pct"] == 40.0
    assert r["pickup_bookings"] == 300


def test_last_year_is_the_equivalent_snapshot_not_the_finished_month():
    # October 2025 ended at 80% (2480 nights). The comparison that matters is
    # where it stood on 25 Aug 2025 — 40% — otherwise every future month looks
    # catastrophically behind a completed one.
    branch = _FakeBranch(BID, "MEANDER Taipei", 100)
    db = _FakeDB(
        [
            [_row(BID, "2026-10", final=1550, otb=1550, pickup=620)],
            [_row(BID, "2025-10", final=2480, otb=1240, pickup=465)],
        ],
        [branch],
    )
    out = tool_get_booking_pace(db, dict(Q4), None)
    r = out["rows"][0]

    assert r["last_year"]["stay_month"] == "2025-10"
    assert r["last_year"]["otb_occ_pct"] == 40.0
    assert r["last_year"]["pickup_occ_pct"] == 15.0
    assert r["last_year"]["final_occ_pct"] == 80.0
    # Gaps in percentage points, growth as a percentage of last year's pickup.
    assert r["vs_last_year"]["pickup_occ_pts"] == 5.0
    assert r["vs_last_year"]["otb_occ_pts"] == 10.0
    assert r["vs_last_year"]["pickup_room_nights_delta"] == 155
    assert r["vs_last_year"]["pickup_growth_pct"] == 33.33

    # And the year-ago window sits on the same calendar days.
    assert out["last_year_booking_window"]["booked_from"] == "2025-06-27"
    assert out["last_year_booking_window"]["booked_to"] == "2025-08-25"
    assert out["last_year_booking_window"]["days"] == out["booking_window"]["days"]


def test_group_total_sums_room_nights_instead_of_averaging_branches():
    # A 138-room branch and a 10-room one do not weigh the same: averaging
    # their percentages would report 25% where the group is really 45.45%.
    big, small = _FakeBranch(BID, "MEANDER Taipei", 100), _FakeBranch("bid-2", "MEANDER 1948", 10)
    db = _FakeDB(
        [
            [_row(BID, "2026-10", final=1550, otb=1550, pickup=620),
             _row("bid-2", "2026-10", final=0, otb=0, pickup=0)],
            [],
        ],
        [big, small],
    )
    out = tool_get_booking_pace(db, dict(Q4), None)
    g = out["group_total"][0]

    assert g["available_room_nights"] == 3410      # (100 + 10) × 31
    assert g["otb_occ_pct"] == 45.45
    assert g["pickup_occ_pct"] == 18.18


def test_a_month_with_no_rows_reports_zero_not_a_missing_row():
    branch = _FakeBranch(BID, "MEANDER Taipei", 100)
    db = _FakeDB([[], []], [branch])
    out = tool_get_booking_pace(
        db, {"stay_month_from": "2026-10", "stay_month_to": "2026-12",
             "booked_from": "2026-06-27", "booked_to": "2026-08-25"}, None,
    )
    assert [r["stay_month"] for r in out["rows"]] == ["2026-10", "2026-11", "2026-12"]
    assert all(r["otb_room_nights"] == 0 and r["pickup_occ_pct"] == 0.0 for r in out["rows"])
    # Inventory still differs per month — November is a 30-day month.
    assert [r["available_room_nights"] for r in out["rows"]] == [3100, 3000, 3100]


def test_nights_are_expanded_and_clipped_to_the_stay_month():
    branch = _FakeBranch(BID, "MEANDER Taipei", 100)
    db = _FakeDB([[], []], [branch])
    tool_get_booking_pace(db, dict(Q4), None)
    sql = db.sql[0]

    # One row per night, month attributed from the night rather than check-in,
    # and the span clipped after expansion.
    assert "generate_series" in sql
    assert "date_trunc('month', stay_date)" in sql
    assert "WHERE stay_date >= :span_start AND stay_date <= :span_end" in sql
    # Cancelled / no-show and maintenance never occupy a room.
    assert "'cancelled'" in sql and "'no_show'" in sql
    assert "'maintenance'" in sql
    # The pickup slice is cut on booking date, the snapshot on the as-of date.
    assert ":bk_from AND :bk_to" in sql
    assert "reservation_date <= :as_of" in sql

    params = db.params[0]
    assert params["span_start"] == date(2026, 10, 1)
    assert params["span_end"] == date(2026, 10, 31)
    assert params["bk_from"] == date(2026, 6, 27)
    assert params["as_of"] == date(2026, 8, 25)


def test_compare_last_year_off_skips_the_second_query():
    branch = _FakeBranch(BID, "MEANDER Taipei", 100)
    db = _FakeDB([[_row(BID, "2026-10", final=1550, otb=1550, pickup=620)]], [branch])
    out = tool_get_booking_pace(db, dict(Q4, compare_last_year=False), None)

    assert len(db.sql) == 1
    assert out["last_year_booking_window"] is None
    assert "last_year" not in out["rows"][0]


def test_branch_filter_scopes_both_the_sql_and_the_rows():
    big, small = _FakeBranch(BID, "MEANDER Taipei", 100), _FakeBranch("bid-2", "MEANDER 1948", 10)
    db = _FakeDB([[], []], [big, small])
    out = tool_get_booking_pace(db, dict(Q4, branch_id=BID), None)

    assert db.params[0]["bid"] == BID
    assert {r["branch_id"] for r in out["rows"]} == {BID}


def test_days_default_window_is_the_last_60_days_ending_today():
    branch = _FakeBranch(BID, "MEANDER Taipei", 100)
    db = _FakeDB([[], []], [branch])
    out = tool_get_booking_pace(db, {"stay_month_from": "2026-10", "stay_month_to": "2026-10"}, None)
    assert out["booking_window"]["days"] == 60
    assert out["booking_window"]["booked_to"] == date.today().isoformat()


def test_booking_pace_is_advertised_to_the_chat_model():
    names = {t["name"] for t in TOOL_DEFS}
    assert "get_booking_pace" in names
    assert names == set(TOOL_HANDLERS.keys())
    assert TOOL_HANDLERS["get_booking_pace"] is chat_tools.tool_get_booking_pace

    desc = next(t for t in TOOL_DEFS if t["name"] == "get_booking_pace")["description"]
    # The wording the assistant matches on when it is asked this question.
    for phrase in ("pickup", "pace", "on the books", "otb_occ_pct", "pickup_occ_pct"):
        assert phrase in desc


def test_note_warns_that_last_year_lost_its_later_cancellations():
    branch = _FakeBranch(BID, "MEANDER Taipei", 100)
    db = _FakeDB([[], []], [branch])
    note = tool_get_booking_pace(db, dict(Q4), None)["note"]
    assert "cancelled" in note and "LAST YEAR CAVEAT" in note


# ── Room / Dorm scope ───────────────────────────────────────────────────────
#
# The private-room half of the Q4 campaign sheet could not be built from this
# tool at all: it only ever counted the whole branch against total_rooms, which
# mixes 30 private rooms with 108 dorm beds. Filtering the nights without also
# moving the denominator would be worse than not filtering — private-room
# occupancy would read at a third of its real value.

def test_room_category_filters_the_nights_and_moves_the_denominator():
    # Taipei: 138 units in all, of which 30 are private rooms. 292 private
    # room-nights in a 31-day month is 31.40% of the private inventory (930) —
    # against the whole 4,278 it would read 6.83% and mean nothing.
    branch = _FakeBranch(BID, "MEANDER Taipei", 138, room_count=30, dorm_count=108)
    db = _FakeDB([[_row(BID, "2026-10", final=292, otb=292, pickup=292)], []], [branch])
    out = tool_get_booking_pace(db, dict(Q4, room_category="Room"), None)

    row = out["rows"][0]
    assert row["available_room_nights"] == 930
    assert row["units_in_scope"] == 30
    assert row["total_rooms"] == 138          # still reported, for context
    assert row["pickup_occ_pct"] == 31.4

    assert "r.room_type_category = :rcat" in db.sql[0]
    assert db.params[0]["rcat"] == "Room"
    assert out["room_category"] == "Room"


def test_dorm_scope_counts_against_the_bed_inventory():
    branch = _FakeBranch(BID, "MEANDER Taipei", 138, room_count=30, dorm_count=108)
    db = _FakeDB([[_row(BID, "2026-10", final=0, otb=0, pickup=1674)], []], [branch])
    out = tool_get_booking_pace(db, dict(Q4, room_category="Dorm"), None)

    assert db.params[0]["rcat"] == "Dorm"
    assert out["rows"][0]["available_room_nights"] == 108 * 31
    assert out["rows"][0]["pickup_occ_pct"] == 50.0


def test_last_year_snapshot_carries_the_same_scope():
    # A private-room pace compared against last year's whole branch would be
    # nonsense, so the filter has to reach the year-ago query too.
    branch = _FakeBranch(BID, "MEANDER Taipei", 138, room_count=30, dorm_count=108)
    db = _FakeDB([[], []], [branch])
    tool_get_booking_pace(db, dict(Q4, room_category="Room"), None)

    assert len(db.sql) == 2
    assert all("r.room_type_category = :rcat" in sql for sql in db.sql)
    assert [p["rcat"] for p in db.params] == ["Room", "Room"]


def test_no_room_category_leaves_the_query_and_the_denominator_alone():
    branch = _FakeBranch(BID, "MEANDER Taipei", 138, room_count=30, dorm_count=108)
    db = _FakeDB([[_row(BID, "2026-10", final=358, otb=358, pickup=330)], []], [branch])
    out = tool_get_booking_pace(db, dict(Q4), None)

    assert "room_type_category" not in db.sql[0]
    assert "rcat" not in db.params[0]
    assert out["rows"][0]["available_room_nights"] == 138 * 31
    assert out["room_category"] == "all"


def test_room_category_is_case_insensitive_and_junk_falls_back_to_whole_branch():
    branch = _FakeBranch(BID, "MEANDER Taipei", 138, room_count=30, dorm_count=108)

    db = _FakeDB([[], []], [branch])
    assert tool_get_booking_pace(db, dict(Q4, room_category="room"), None)["room_category"] == "Room"
    assert db.params[0]["rcat"] == "Room"

    # An unrecognised value must not silently bind and return zero rows.
    db = _FakeDB([[], []], [branch])
    out = tool_get_booking_pace(db, dict(Q4, room_category="suite"), None)
    assert out["room_category"] == "all"
    assert "rcat" not in db.params[0]


def test_branch_with_no_beds_reports_no_occupancy_rather_than_dividing_by_zero():
    # Osaka is 71 private rooms and 0 dorm beds. Asked for its dorm pace the
    # answer is "there is no such inventory", not a crash and not 0%.
    branch = _FakeBranch("bid-osaka", "MEANDER Osaka", 71, room_count=71, dorm_count=0)
    db = _FakeDB([[], []], [branch])
    out = tool_get_booking_pace(db, dict(Q4, room_category="Dorm"), None)

    row = out["rows"][0]
    assert row["available_room_nights"] == 0
    assert row["pickup_occ_pct"] is None
    assert row["otb_occ_pct"] is None


def test_note_states_which_inventory_the_percentages_are_against():
    branch = _FakeBranch(BID, "MEANDER Taipei", 138, room_count=30, dorm_count=108)

    db = _FakeDB([[], []], [branch])
    assert "total_room_count" in tool_get_booking_pace(db, dict(Q4, room_category="Room"), None)["note"]

    db = _FakeDB([[], []], [branch])
    assert "total_dorm_count" in tool_get_booking_pace(db, dict(Q4, room_category="Dorm"), None)["note"]

    db = _FakeDB([[], []], [branch])
    note = tool_get_booking_pace(db, dict(Q4), None)["note"]
    assert "total_rooms mixes private rooms with dorm beds" in note


def test_room_category_is_advertised_to_the_chat_model():
    schema = next(t for t in TOOL_DEFS if t["name"] == "get_booking_pace")["input_schema"]
    prop = schema["properties"]["room_category"]
    assert prop["enum"] == ["Room", "Dorm"]
    assert "private" in prop["description"]
