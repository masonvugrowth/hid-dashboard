import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Provide dummy env vars so config.py does not fail during import in tests."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("CLOUDBEDS_API_KEY", "test_key")
    monkeypatch.setenv("EXCHANGE_RATE_API_KEY", "test_rate_key")
