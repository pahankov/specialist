"""Tests for log level resolution (P1-4)."""
from app.config import Settings


class TestLogLevel:
    def test_debug_by_default_locally(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.setenv("APP_ENV", "development")
        assert Settings().log_level == "DEBUG"

    def test_info_in_production(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.setenv("APP_ENV", "production")
        assert Settings().log_level == "INFO"

    def test_explicit_level_wins(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("LOG_LEVEL", "warning")
        assert Settings().log_level == "WARNING"
