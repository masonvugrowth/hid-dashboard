"""rate_plan_pattern_filter — the match rule behind ?rate_plan= on the public API."""
from app.services.crm_filters import rate_plan_pattern_filter


def _sql(clause):
    """Compiled SQL. The default dialect renders ILIKE as lower() LIKE lower()."""
    return str(clause.compile(compile_kwargs={"literal_binds": True})).lower()


def test_matches_rate_plan_name_and_room_type():
    sql = _sql(rate_plan_pattern_filter(["EARLY26 2 NIGHTS"]))
    assert "reservations.rate_plan_name" in sql
    assert "reservations.room_type" in sql
    assert sql.count("like lower(") == 2
    assert "%early26 2 nights%" in sql


def test_multiple_patterns_are_ored():
    sql = _sql(
        rate_plan_pattern_filter(["EARLY26 2 NIGHTS", "EARLY26 3+ NIGHTS"])
    )
    assert sql.count("like lower(") == 4
    assert "%early26 3+ nights%" in sql
    assert " and " not in sql


def test_blank_and_empty_input_returns_none():
    assert rate_plan_pattern_filter(None) is None
    assert rate_plan_pattern_filter([]) is None
    assert rate_plan_pattern_filter(["", "   "]) is None
