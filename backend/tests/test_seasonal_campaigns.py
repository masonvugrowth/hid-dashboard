"""Seasonal Campaign tab — the ads/reality join and its cost arithmetic.

Three things are easy to get wrong here and expensive when they are:

1. Ad spend can be unavailable (Ads Platform down, or a Google campaign with
   no ad-level rows). A 0 in that slot makes an infinite ROAS look like a
   real result, so the whole cost chain has to stay None instead.
2. The campaign's cost % is charged on ACTUAL revenue, never on the smaller
   ad-attributed revenue — the discount is owed on every booking that came in
   on the rate plan, however the guest found it.
3. Zeabur does not run Alembic on deploy, so the table is missing for the
   window between this landing and POST /api/sync/run-migrations.
"""
from datetime import date

import pytest

from app.services import seasonal_campaigns as sc

_D = date(2026, 9, 1)


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def order_by(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows=(), raises=False):
        self._rows = list(rows)
        self._raises = raises
        self.rolled_back = False

    def query(self, *a, **k):
        if self._raises:
            raise RuntimeError('relation "seasonal_campaigns" does not exist')
        return _FakeQuery(self._rows)

    def rollback(self):
        self.rolled_back = True


class _Campaign:
    # Ads named by default: the interesting cases all have an ad campaign
    # behind them. Pass ads=() for the rate-plan-only case.
    def __init__(self, name="Tet 2027", cost_pct=0, ads=("TET2027",), plans=(),
                 is_active=True, notes=None):
        self.id = "c-1"
        self.name = name
        self.ads_campaign_names = list(ads)
        self.rate_plan_names = list(plans)
        self.cost_pct = cost_pct
        self.notes = notes
        self.is_active = is_active


class TestMissingTableIsContained:
    def test_list_is_empty_instead_of_raising(self):
        assert sc.list_campaigns(_FakeSession(raises=True)) == []

    def test_and_rolls_the_session_back(self):
        """A failed statement poisons the transaction; without a rollback the
        rest of the page's queries fail too."""
        db = _FakeSession(raises=True)
        sc.list_campaigns(db)
        assert db.rolled_back is True


class TestCleanPatterns:
    def test_trims_and_drops_blanks(self):
        assert sc.clean_patterns([" TET2027 ", "", "   ", "Tet Early Bird"]) == [
            "TET2027", "Tet Early Bird",
        ]

    def test_dedupes_case_insensitively_keeping_the_first_spelling(self):
        assert sc.clean_patterns(["TET2027", "tet2027"]) == ["TET2027"]

    def test_none_is_an_empty_list(self):
        assert sc.clean_patterns(None) == []


class TestRoas:
    def test_no_cost_means_no_roas_rather_than_zero(self):
        """A campaign that spent nothing has no ROAS; 0 reads as 'it failed',
        which is the opposite of what the data says."""
        assert sc._roas(1_000_000, 0) is None
        assert sc._roas(1_000_000, None) is None

    def test_divides_and_rounds(self):
        assert sc._roas(300, 100) == 3.0
        assert sc._roas(1_000, 333) == 3.0


class TestSpendConversion:
    SCOPE = {
        "ad_ids": {"a1", "a2"},
        "campaign_ids": {"c1"},
        "currency_by_ad": {
            "a1": {"account_id": "acc1", "branch_currency": "TWD"},
            "a2": {"account_id": "acc2", "branch_currency": "VND"},
        },
    }

    @staticmethod
    def _rate(cur):
        return {"VND": 1.0, "TWD": 830.0}.get((cur or "").upper())

    def test_each_ad_converts_at_its_own_account_currency(self):
        metrics = {
            "a1": {"spend": 100, "spend_vnd": None, "currency": "TWD"},
            "a2": {"spend": 5_000, "spend_vnd": None, "currency": "VND"},
        }
        assert sc._spend_vnd(self.SCOPE, metrics, self._rate) == 100 * 830 + 5_000

    def test_a_vnd_figure_from_upstream_wins_over_converting_ourselves(self):
        metrics = {"a1": {"spend": 100, "spend_vnd": 12_345, "currency": "TWD"}}
        assert sc._spend_vnd(self.SCOPE, metrics, self._rate) == 12_345

    def test_falls_back_to_the_branch_currency_when_the_row_has_none(self):
        metrics = {"a1": {"spend": 100, "spend_vnd": None, "currency": None}}
        assert sc._spend_vnd(self.SCOPE, metrics, self._rate) == 83_000

    def test_an_unconvertible_row_is_dropped_not_counted_raw(self):
        """Adding a JPY figure to a VND total would silently under-report by
        two orders of magnitude — worse than leaving it out."""
        scope = {
            "ad_ids": {"a1"},
            "campaign_ids": set(),
            "currency_by_ad": {"a1": {"account_id": None, "branch_currency": "JPY"}},
        }
        metrics = {"a1": {"spend": 100, "spend_vnd": None, "currency": "JPY"}}
        assert sc._spend_vnd(scope, metrics, self._rate) == 0.0

    def test_ads_with_no_metrics_row_contribute_nothing(self):
        assert sc._spend_vnd(self.SCOPE, {}, self._rate) == 0.0


def _stub_sides(monkeypatch, *, spend_vnd=0.0, ads=(0, 0.0), actual=(0, 0, 0.0),
                metrics=None):
    monkeypatch.setattr(sc, "_ad_scope", lambda *a, **k: {
        "ad_ids": {"a1"}, "campaign_ids": {"c1"}, "currency_by_ad": {},
    })
    monkeypatch.setattr(sc, "fetch_ad_metrics", lambda *a, **k: metrics)
    monkeypatch.setattr(sc, "_spend_vnd", lambda *a, **k: spend_vnd)
    monkeypatch.setattr(sc, "_ads_bookings", lambda *a, **k: ads)
    monkeypatch.setattr(sc, "actual_bookings", lambda *a, **k: actual)


def _build(campaign, **kw):
    return sc.build_rows(
        _FakeSession(), [campaign], None, None, None,
        status_filter=None, source_filter=None, rev_col=None,
        rate_for=lambda cur: 1.0,
        to_view_currency=lambda vnd: vnd,
        **kw,
    )[0]


class TestRowArithmetic:
    def test_cost_pct_is_charged_on_actual_revenue_not_ad_revenue(self, monkeypatch):
        _stub_sides(
            monkeypatch, metrics={}, spend_vnd=10_000_000,
            ads=(5, 200_000_000),          # ad-attributed revenue is smaller
            actual=(12, 24, 500_000_000),  # every booking on the rate plan
        )
        row = _build(_Campaign(cost_pct=20))
        assert row["campaign_cost"] == 100_000_000       # 20% of ACTUAL
        assert row["total_cost"] == 110_000_000          # + ad spend
        assert row["roas_actual"] == round(500_000_000 / 110_000_000, 2)

    def test_ads_roas_uses_ad_attributed_revenue_over_spend_alone(self, monkeypatch):
        _stub_sides(monkeypatch, metrics={}, spend_vnd=10_000_000,
                    ads=(5, 40_000_000), actual=(12, 24, 500_000_000))
        row = _build(_Campaign(cost_pct=20))
        assert row["roas_ads"] == 4.0

    def test_zero_cost_pct_leaves_the_real_roas_on_ad_spend_alone(self, monkeypatch):
        _stub_sides(monkeypatch, metrics={}, spend_vnd=10_000_000,
                    ads=(5, 40_000_000), actual=(12, 24, 50_000_000))
        row = _build(_Campaign(cost_pct=0))
        assert row["campaign_cost"] == 0
        assert row["total_cost"] == 10_000_000
        assert row["roas_actual"] == 5.0

    def test_the_two_sides_are_reported_separately(self, monkeypatch):
        """The gap between ad-attributed and actual bookings is the reason the
        tab exists — neither may be quietly substituted for the other."""
        _stub_sides(monkeypatch, metrics={}, spend_vnd=1_000,
                    ads=(5, 40_000_000), actual=(12, 24, 500_000_000))
        row = _build(_Campaign())
        assert (row["ads_bookings"], row["actual_bookings"]) == (5, 12)
        assert (row["ads_revenue"], row["actual_revenue"]) == (40_000_000, 500_000_000)


class TestSpendUnavailable:
    def test_spend_stays_none_rather_than_zero(self, monkeypatch):
        _stub_sides(monkeypatch, metrics=None, ads=(5, 40_000_000),
                    actual=(12, 24, 500_000_000))
        row = _build(_Campaign(cost_pct=20))
        assert row["spend"] is None
        assert row["spend_available"] is False

    def test_and_neither_total_cost_nor_the_real_roas_is_invented(self, monkeypatch):
        """A missing spend makes the true cost unknown, so the true ROAS is
        unknown too — 25x on a cost of 'just the discount' would be a lie."""
        _stub_sides(monkeypatch, metrics=None, ads=(5, 40_000_000),
                    actual=(12, 24, 500_000_000))
        row = _build(_Campaign(cost_pct=20))
        assert row["total_cost"] is None
        assert row["roas_actual"] is None
        assert row["roas_ads"] is None

    def test_the_rate_plan_columns_still_report(self, monkeypatch):
        _stub_sides(monkeypatch, metrics=None, ads=(0, 0.0),
                    actual=(12, 24, 500_000_000))
        row = _build(_Campaign(cost_pct=20))
        assert row["actual_bookings"] == 12
        assert row["actual_revenue"] == 500_000_000
        assert row["campaign_cost"] == 100_000_000


class TestRatePlanOnlyCampaign:
    def test_no_ad_names_means_no_upstream_call_and_no_warning(self, monkeypatch):
        """A campaign sold on a rate plan with no ads behind it really did
        spend zero. Calling out just to fail would put an "Ads Platform
        unavailable" banner on a tab where spend was never part of the answer."""
        called = []
        _stub_sides(monkeypatch, metrics=None, actual=(12, 24, 500_000_000))
        monkeypatch.setattr(
            sc, "fetch_ad_metrics",
            lambda *a, **k: called.append(1) or None,
        )
        row = _build(_Campaign(cost_pct=10, ads=()))
        assert called == []
        assert row["spend"] == 0
        assert row["spend_available"] is True
        assert row["total_cost"] == 50_000_000
        assert row["roas_actual"] == 10.0


class TestCurrencyView:
    def test_money_passes_through_the_view_converter(self, monkeypatch):
        """Single-branch views read in the branch's own currency; the ads side
        arrives in VND and has to be converted like everything else."""
        _stub_sides(monkeypatch, metrics={}, spend_vnd=830_000,
                    ads=(2, 8_300_000), actual=(3, 6, 16_600_000))
        row = sc.build_rows(
            _FakeSession(), [_Campaign(cost_pct=50)], None, None, None,
            status_filter=None, source_filter=None, rev_col=None,
            rate_for=lambda cur: 830.0,
            to_view_currency=lambda vnd: vnd / 830.0,
        )[0]
        assert row["spend"] == 1_000
        assert row["ads_revenue"] == 10_000
        # actual_revenue comes from the reservation query already in the view
        # currency, so it is NOT converted a second time.
        assert row["actual_revenue"] == 16_600_000


class TestFetchAdMetrics:
    def test_returns_none_when_every_platform_fails(self, monkeypatch):
        class _Client:
            def get_accounts(self):
                return []

            def get_ads_metrics(self, *a, **k):
                raise RuntimeError("upstream down")

        monkeypatch.setattr(sc, "get_client", lambda: _Client())
        assert sc.fetch_ad_metrics(_D, _D) is None

    def test_sums_spend_per_ad_across_platforms(self, monkeypatch):
        class _Client:
            def get_accounts(self):
                return [{"id": "acc1", "currency": "twd"}]

            def get_ads_metrics(self, df, dt, platform=None):
                if platform == "meta":
                    return [{"ad_id": "a1", "spend": 100, "account_id": "acc1"}]
                if platform == "google":
                    return [{"ad_id": "a1", "spend": 50, "account_id": "acc1"}]
                return []

        monkeypatch.setattr(sc, "get_client", lambda: _Client())
        out = sc.fetch_ad_metrics(_D, _D)
        assert out["a1"]["spend"] == 150
        assert out["a1"]["currency"] == "TWD"

    def test_a_client_that_cannot_be_built_is_not_an_empty_result(self, monkeypatch):
        def _boom():
            raise RuntimeError("no api key")

        monkeypatch.setattr(sc, "get_client", _boom)
        assert sc.fetch_ad_metrics(_D, _D) is None



@pytest.mark.parametrize("raw,expected", [
    ({"spend": "12.5"}, 12.5),
    ({"cost": 7}, 7.0),
    ({"spend": None, "cost": 3}, 3.0),
    ({}, 0.0),
    ({"spend": "not a number"}, 0.0),
])
def test_num_reads_whichever_spend_key_upstream_used(raw, expected):
    """The export's row shape is not in its OpenAPI schema, so the reader has
    to tolerate spend / cost / spend_native without zeroing the column."""
    assert sc._num(raw.get("spend"), raw.get("cost"),
                   raw.get("spend_native")) == expected
