"""KOL budget actuals: undoing the Engine's currency conversion.

KOL costs are typed into the KOL Engine in VND. GET /api/sync/budgets hands
them back in the hotel's budget currency, divided by the Engine's own rates
(820 TWD / 170 JPY), and ignores every spelling of a currency= override.
`fetch_kol_yearly` used HiD's display rates (830 / 165) to multiply back, so
every TWD branch landed 1.22% high and every JPY branch 2.94% low.

These pin the round trip to identity: whatever VND figure the Engine divided,
that same figure comes back out.
"""
from unittest.mock import patch

from app.services import upstream_actuals
from app.services.upstream_actuals import fetch_kol_yearly

TAIPEI = "c07ddc13-524d-4600-b3d8-5cc1871a0286"


def _response(currency, months):
    return {"data": {"currency": currency,
                     "monthly_breakdown": [{"month": m, "actual": a}
                                           for m, a in months]}}


def _run(currency, months):
    with patch.object(upstream_actuals.settings, "KOL_SYNC_API_KEY", "k"), \
         patch.object(upstream_actuals, "_fetch_json",
                      return_value=_response(currency, months)):
        return fetch_kol_yearly(TAIPEI, 2026)


class TestRoundTripIsLossless:
    def test_twd_branch_returns_the_vnd_that_was_typed_in(self):
        # 800,000 VND / 820 is what the Engine actually returns for Taipei Jan.
        out = _run("TWD", [(1, 800000 / 820), (8, 500000 / 820)])
        assert out[1] == 800000.00   # not 809,756.10
        assert out[8] == 500000.00   # not 506,097.56

    def test_jpy_branch_returns_the_vnd_that_was_typed_in(self):
        out = _run("JPY", [(1, 35910000 / 170), (6, 500000 / 170)])
        assert out[1] == 35910000.00  # not 34,853,823.48
        assert out[6] == 500000.00

    def test_vnd_branch_passes_through_untouched(self):
        out = _run("VND", [(3, 1600000), (8, 500000)])
        assert out[3] == 1600000.00
        assert out[8] == 500000.00


class TestUnknownCurrency:
    def test_falls_back_to_treating_the_figure_as_vnd(self):
        out = _run("USD", [(1, 1234.0)])
        assert out[1] == 1234.00


class TestUpstreamFailure:
    def test_no_api_key_returns_nothing_rather_than_zeros(self):
        with patch.object(upstream_actuals.settings, "KOL_SYNC_API_KEY", ""):
            assert fetch_kol_yearly(TAIPEI, 2026) == {}

    def test_unreachable_engine_returns_nothing_rather_than_zeros(self):
        with patch.object(upstream_actuals.settings, "KOL_SYNC_API_KEY", "k"), \
             patch.object(upstream_actuals, "_fetch_json", return_value=None):
            assert fetch_kol_yearly(TAIPEI, 2026) == {}
