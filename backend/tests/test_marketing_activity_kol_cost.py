"""Marketing Activity KOL cost source.

The KOL row used to take its cost from Budget Planner's ActualsCache, which
reaches the KOL Engine's Budget module. That endpoint answers in the hotel's
budget currency, having divided the stored VND by the Engine's own rates
(820 TWD / 170 JPY), and `fetch_kol_yearly` multiplied back by our hardcoded
830 / 165 — so August 2026's clean 1,000,000 VND rendered as 1,006,097.56.

Cost now reads `cost_vnd` off the same /api/public/kol-revenue payload the KOL
revenue comes from, which the Engine has already converted at its own rates.
"""
from datetime import date
from unittest.mock import patch

from app.routers import marketing_activity as ma

AUG_FROM, AUG_TO = date(2026, 8, 1), date(2026, 8, 31)

OANI = "41b5eb59-016d-442f-8c47-455a9bc567a3"
TAIPEI = "c07ddc13-524d-4600-b3d8-5cc1871a0286"

# Shape of the live August 2026 response, trimmed to the fields read here.
AUG_PAYLOAD = {
    "totals": {"revenue": 1794697800, "bookings": 223, "cost": 1000000,
               "currency": "VND"},
    "branches": [
        {"hotel_id": OANI, "currency": "TWD", "cost": 0, "cost_vnd": 0},
        {"hotel_id": TAIPEI, "currency": "VND", "cost": 500000, "cost_vnd": 500000},
    ],
}


class _Branch:
    def __init__(self, name="MEANDER Taipei", currency="TWD"):
        self.name = name
        self.currency = currency


class _DB:
    """Stands in for the Session — only ever asked for one Branch row."""
    def __init__(self, branch=None):
        self._branch = branch

    def query(self, *_a):
        return self

    def filter(self, *_a):
        return self

    def first(self):
        return self._branch


def _payload_for(*_a, **kw):
    return AUG_PAYLOAD


class TestCostComesFromKolRevenuePayload:
    def test_all_branches_uses_org_total_verbatim(self):
        with patch.object(ma, "fetch_kol_revenue", side_effect=_payload_for):
            cost = ma._fetch_kol_cost_vnd(_DB(), None, AUG_FROM, AUG_TO)
        # Not 1,006,097.56 — no round trip through 820 → 830.
        assert cost == 1000000

    def test_single_branch_uses_that_branch_cost_vnd(self):
        db = _DB(_Branch("MEANDER Taipei", "TWD"))
        with patch.object(ma, "fetch_kol_revenue", side_effect=_payload_for):
            cost = ma._fetch_kol_cost_vnd(db, "any-branch-id", AUG_FROM, AUG_TO)
        assert cost == 500000

    def test_branch_absent_from_response_is_zero_not_a_failure(self):
        db = _DB(_Branch("MEANDER Osaka", "JPY"))
        with patch.object(ma, "fetch_kol_revenue", side_effect=_payload_for):
            cost = ma._fetch_kol_cost_vnd(db, "any-branch-id", AUG_FROM, AUG_TO)
        assert cost == 0.0

    def test_ytd_range_sums_every_month(self):
        with patch.object(ma, "fetch_kol_revenue", side_effect=_payload_for):
            cost = ma._fetch_kol_cost_vnd(
                _DB(), None, date(2026, 1, 1), date(2026, 8, 31))
        assert cost == 8 * 1000000


class TestFallback:
    def test_engine_unreachable_keeps_budget_planner_actuals(self):
        with patch.object(ma, "fetch_kol_revenue", return_value=None):
            cost = ma._kol_cost_for_view(
                _DB(), None, AUG_FROM, AUG_TO, False, fallback=1006097.56)
        # None, not 0 — a 0 here would blank the KOL ROAS instead of degrading.
        assert cost == 1006097.56

    def test_one_bad_month_in_a_range_falls_back_whole(self):
        calls = {"n": 0}

        def flaky(*_a, **kw):
            calls["n"] += 1
            return None if kw["month"] == 3 else AUG_PAYLOAD

        with patch.object(ma, "fetch_kol_revenue", side_effect=flaky):
            cost = ma._kol_cost_for_view(
                _DB(), None, date(2026, 1, 1), date(2026, 8, 31), False,
                fallback=42.0)
        assert cost == 42.0

    def test_unmappable_branch_name_falls_back(self):
        db = _DB(_Branch("Some New Property", "VND"))
        with patch.object(ma, "fetch_kol_revenue", side_effect=_payload_for):
            cost = ma._kol_cost_for_view(
                db, "any-branch-id", AUG_FROM, AUG_TO, True, fallback=7.0)
        assert cost == 7.0


class TestNativeCurrencyView:
    def test_single_branch_native_converts_from_vnd(self):
        db = _DB(_Branch("MEANDER Taipei", "TWD"))
        with patch.object(ma, "fetch_kol_revenue", side_effect=_payload_for), \
             patch.object(ma, "_get_rate_to_vnd", return_value=830.0):
            cost = ma._kol_cost_for_view(
                db, "any-branch-id", AUG_FROM, AUG_TO, True, fallback=0.0)
        assert cost == round(500000 / 830.0, 2)

    def test_all_branches_view_stays_vnd(self):
        with patch.object(ma, "fetch_kol_revenue", side_effect=_payload_for):
            cost = ma._kol_cost_for_view(
                _DB(), None, AUG_FROM, AUG_TO, False, fallback=0.0)
        assert cost == 1000000
