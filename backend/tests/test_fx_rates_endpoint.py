"""Tests for GET /api/metrics/fx-rates — the FX transparency panel's source."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.services.currency as currency_module
from app.database import get_db
from app.routers import metrics
from app.services.currency import _rate_cache


@pytest.fixture(autouse=True)
def clear_cache():
    _rate_cache.clear()
    yield
    _rate_cache.clear()


@pytest.fixture
def client():
    api = FastAPI()
    api.include_router(metrics.router, prefix="/api/metrics")

    def fake_db():
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            ("Meander Taipei", "TWD"),
            ("Meander Osaka", "JPY"),
            ("Meander Saigon", "VND"),
        ]
        yield db

    api.dependency_overrides[get_db] = fake_db
    return TestClient(api)


def _rate(payload, currency):
    return next(r for r in payload["data"]["rates"] if r["currency"] == currency)


def test_reports_fallback_when_cache_is_empty(client, monkeypatch):
    monkeypatch.setattr(currency_module.settings, "EXCHANGE_RATE_API_KEY", "placeholder_key")

    resp = client.get("/api/metrics/fx-rates")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["data"]["api_key_configured"] is False

    twd = _rate(payload, "TWD")
    assert twd["source"] == "fallback"
    assert twd["rate_vnd_in_use"] == 830.0
    assert twd["branches"] == ["Meander Taipei"]
    # No key means no live comparison to make — say so instead of showing a rate.
    assert twd["live_rate_vnd"] is None
    assert "EXCHANGE_RATE_API_KEY" in twd["live_error"]

    assert _rate(payload, "VND")["rate_vnd_in_use"] == 1.0


def test_reports_cached_rate_and_drift_vs_live(client, monkeypatch):
    monkeypatch.setattr(currency_module.settings, "EXCHANGE_RATE_API_KEY", "real_key")
    _rate_cache[("TWD", "VND")] = (830.0, date.today())

    with patch("app.services.currency.probe_live_rate", new=AsyncMock(return_value=(800.0, None))):
        payload = client.get("/api/metrics/fx-rates").json()

    twd = _rate(payload, "TWD")
    assert twd["source"] == "cache_today"
    assert twd["rate_vnd_in_use"] == 830.0
    assert twd["live_rate_vnd"] == 800.0
    assert twd["drift_vs_live_pct"] == 3.75


def test_flags_a_stale_cache_entry(client, monkeypatch):
    monkeypatch.setattr(currency_module.settings, "EXCHANGE_RATE_API_KEY", "real_key")
    _rate_cache[("JPY", "VND")] = (170.0, date(2026, 1, 1))

    with patch("app.services.currency.probe_live_rate", new=AsyncMock(return_value=(163.7, None))):
        payload = client.get("/api/metrics/fx-rates").json()

    jpy = _rate(payload, "JPY")
    assert jpy["source"] == "cache_stale"
    assert jpy["cached_on"] == "2026-01-01"
    assert jpy["rate_vnd_in_use"] == 170.0


def test_refresh_updates_the_cache(client, monkeypatch):
    monkeypatch.setattr(currency_module.settings, "EXCHANGE_RATE_API_KEY", "real_key")
    _rate_cache[("TWD", "VND")] = (830.0, date(2026, 1, 1))

    async def fake_refresh(frm, to="VND"):
        _rate_cache[(frm, to)] = (819.0, date.today())
        return 819.0

    with patch("app.services.currency.refresh_rate", new=fake_refresh), \
         patch("app.services.currency.probe_live_rate", new=AsyncMock(return_value=(819.0, None))):
        payload = client.get("/api/metrics/fx-rates", params={"refresh": True}).json()

    twd = _rate(payload, "TWD")
    assert payload["data"]["refreshed"] is True
    assert twd["source"] == "cache_today"
    assert twd["rate_vnd_in_use"] == 819.0
    assert twd["drift_vs_live_pct"] == 0.0
