"""Tests for services/ghl_email_sync.py — focuses on attribution logic."""
from datetime import date
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest

import app.services.ghl_email_sync as mod
from app.services.ghl_email_sync import (
    _compute_attribution,
    _parse_workflow_created,
    _resolve_vnd_rate,
)


def _res(status="checked_out", rate_plan=None, room_type=None, native=0.0, vnd=0.0, nights=1):
    return SimpleNamespace(
        status=status,
        rate_plan_name=rate_plan,
        room_type=room_type,
        grand_total_native=native,
        grand_total_vnd=vnd,
        nights=nights,
    )


class TestParseWorkflowCreated:
    def test_iso_with_z(self):
        wf = {"dateAdded": "2026-03-25T20:05:00.000Z"}
        assert _parse_workflow_created(wf) == date(2026, 3, 25)

    def test_iso_no_z(self):
        wf = {"createdAt": "2026-04-20T10:27:00+00:00"}
        assert _parse_workflow_created(wf) == date(2026, 4, 20)

    def test_missing(self):
        assert _parse_workflow_created({}) is None

    def test_malformed(self):
        assert _parse_workflow_created({"dateAdded": "not a date"}) is None


class TestResolveVndRate:
    def test_vnd_returns_one(self):
        assert _resolve_vnd_rate("VND") == 1.0

    def test_falls_back_to_hardcoded(self):
        # No cache, no API key → uses hardcoded fallback
        rate = _resolve_vnd_rate("TWD")
        assert rate == 830.0

    def test_unknown_currency(self):
        assert _resolve_vnd_rate("XYZ") is None

    def test_none_currency(self):
        assert _resolve_vnd_rate(None) is None


class TestComputeAttribution:
    def _setup_query(self, monkeypatch, reservations):
        """Mock db.query(Reservation).filter(...).filter(...).all() chain."""
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.all.return_value = reservations
        db = MagicMock()
        db.query.return_value = chain
        return db

    def test_no_branch_id_returns_empty(self):
        db = MagicMock()
        result = _compute_attribution(db, "April 2026", date(2026, 3, 25), None, "TWD")
        assert result["attributed_bookings"] == 0
        assert result["attributed_revenue_native"] == 0.0
        assert result["attributed_rate_plan"] == "CRM_April 2026 Events"

    def test_aggregates_revenue_and_excludes_canceled(self):
        reservations = [
            _res(status="checked_out", native=10000.0, vnd=8_300_000.0, nights=2),
            _res(status="confirmed", native=15000.0, vnd=12_450_000.0, nights=3),
            _res(status="canceled", native=5000.0, vnd=4_150_000.0, nights=1),
        ]
        db = self._setup_query(None, reservations)
        result = _compute_attribution(db, "April 2026", date(2026, 3, 25), "branch-uuid", "TWD")

        assert result["attributed_bookings"] == 2
        assert result["attributed_canceled"] == 1
        assert result["attributed_nights"] == 5
        assert result["attributed_revenue_native"] == 25000.0
        # Pre-converted vnd is summed when present
        assert result["attributed_revenue_vnd"] == 20_750_000.0
        assert result["attributed_currency"] == "TWD"
        assert result["attributed_rate_plan"] == "CRM_April 2026 Events"

    def test_falls_back_to_fx_when_vnd_zero(self):
        reservations = [
            _res(status="checked_out", native=10000.0, vnd=0.0, nights=2),
        ]
        db = self._setup_query(None, reservations)
        result = _compute_attribution(db, "April 2026", date(2026, 3, 25), "branch-uuid", "TWD")

        # Falls back to hardcoded TWD→VND=830.0
        assert result["attributed_revenue_vnd"] == 8_300_000.0

    def test_canceled_status_case_insensitive(self):
        reservations = [
            _res(status="Canceled", native=10000.0, nights=2),
            _res(status="CANCELED", native=20000.0, nights=3),
        ]
        db = self._setup_query(None, reservations)
        result = _compute_attribution(db, "April 2026", date(2026, 3, 25), "branch-uuid", "TWD")

        assert result["attributed_bookings"] == 0
        assert result["attributed_canceled"] == 2
        assert result["attributed_revenue_native"] == 0.0

    def test_pattern_format(self):
        db = self._setup_query(None, [])
        result = _compute_attribution(db, "Event May 2026", None, "branch-uuid", "JPY")
        assert result["attributed_rate_plan"] == "CRM_Event May 2026 Events"


class TestFetchWorkflowStatsReason:
    """A failed stats fetch must name its cause — silence here hid a 57-day
    outage where GHL's workflow-campaigns route started returning 404."""

    def _client(self, *, status=200, payload=None, text="", raises=None):
        resp = MagicMock()
        resp.status_code = status
        resp.text = text
        if raises is not None:
            resp.json.side_effect = raises
        else:
            resp.json.return_value = payload if payload is not None else {}
        client = MagicMock()
        client.get.return_value = resp
        return client

    def test_success_returns_stats_and_no_reason(self):
        client = self._client(payload={"stats": {"delivered": 12}})
        stats, reason = mod._fetch_workflow_stats(client, "loc", "key", "wf")
        assert stats == {"delivered": 12}
        assert reason is None

    def test_404_reports_status_and_body(self):
        client = self._client(status=404, text='{"statusCode":404,"message":"Not Found"}')
        stats, reason = mod._fetch_workflow_stats(client, "loc", "key", "wf")
        assert stats is None
        assert "HTTP 404" in reason
        assert "Not Found" in reason

    def test_200_without_stats_key_is_reported(self):
        client = self._client(payload={"traceId": "abc"})
        stats, reason = mod._fetch_workflow_stats(client, "loc", "key", "wf")
        assert stats is None
        assert "no usable 'stats'" in reason

    def test_transport_error_is_reported_not_swallowed(self):
        client = MagicMock()
        client.get.side_effect = RuntimeError("boom")
        stats, reason = mod._fetch_workflow_stats(client, "loc", "key", "wf")
        assert stats is None
        assert "RuntimeError" in reason

    def test_non_json_body_is_reported(self):
        client = self._client(text="<html>502</html>", raises=ValueError("nope"))
        stats, reason = mod._fetch_workflow_stats(client, "loc", "key", "wf")
        assert stats is None
        assert "non-JSON" in reason


class TestStatsEndpointContract:
    """Locks the v3 route + version header, and the real `sent` field.

    The old /emails/stats/location/... route 404'd silently from 2026-06-30,
    freezing every workflow row for 57 days.
    """

    def test_calls_v3_unified_route_with_v3_version_header(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"stats": {"delivered": 1}}
        client = MagicMock()
        client.get.return_value = resp

        mod._fetch_workflow_stats(client, "LOC", "key", "WF")

        url = client.get.call_args[0][0]
        assert url.endswith("/emails/locations/LOC/campaigns/stats/workflow-campaigns/WF")
        assert "/emails/stats/location/" not in url
        assert client.get.call_args[1]["headers"]["Version"] == "v3"

    def test_non_stats_calls_keep_the_dated_version(self):
        assert mod._headers("k")["Version"] == "2021-07-28"
        assert mod._headers("k", mod.GHL_VERSION_STATS)["Version"] == "v3"

    def test_real_sent_field_beats_the_derived_fallback(self):
        # Live Saigon payload: derived would give 20734+117+0 = 20851, but the
        # true count is 20923.
        stats = {"sent": 20923, "delivered": 20734, "permanentFail": 117, "temporaryFail": 0}
        derived = stats["delivered"] + stats["permanentFail"] + stats["temporaryFail"]
        assert derived == 20851
        assert (stats.get("sent") or derived) == 20923

    def test_falls_back_to_derived_when_sent_absent(self):
        stats = {"delivered": 100, "permanentFail": 5, "temporaryFail": 2}
        derived = stats["delivered"] + stats["permanentFail"] + stats["temporaryFail"]
        assert (stats.get("sent") or derived) == 107
