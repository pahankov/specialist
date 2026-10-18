"""Tests for logging setup resilience.

A log file that is not writable (e.g. deploy changed the owner of logs/)
must never crash the app: setup_logging falls back to console-only output.
Prod incident 2026-10-18: beauty-backend crash-looped on PermissionError
while opening logs/app.log left behind by the deploy user.
"""
import logging
import logging.handlers

import pytest

from app import logging_config
from app.logging_config import setup_logging


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """setup_logging mutates global logging state — restore it after each test."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


class TestFileHandlerFallback:
    def test_falls_back_to_console_when_log_file_unwritable(self, monkeypatch):
        def _unwritable(*args, **kwargs):
            raise PermissionError(13, "Permission denied")

        real_file_handler = logging.FileHandler
        monkeypatch.setattr(logging.handlers, "RotatingFileHandler", _unwritable)
        monkeypatch.setattr(logging, "FileHandler", _unwritable)

        setup_logging("INFO")  # must not raise

        root = logging.getLogger()
        assert root.handlers, "консольный хендлер должен остаться"
        assert not any(
            isinstance(h, real_file_handler) for h in root.handlers
        ), "файловый хендлер не должен пережить PermissionError"

    def test_falls_back_when_log_dir_cannot_be_created(
        self, tmp_path, monkeypatch
    ):
        blocker = tmp_path / "blocker"
        blocker.write_text("file, not a dir", encoding="utf-8")
        monkeypatch.setattr(logging_config, "LOG_DIR", blocker / "logs")

        setup_logging("INFO")  # must not raise

        root = logging.getLogger()
        assert root.handlers
        assert not any(isinstance(h, logging.FileHandler) for h in root.handlers)

    def test_file_handler_used_when_log_dir_writable(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)

        setup_logging("INFO")
        logging.getLogger().info("hello")

        root = logging.getLogger()
        assert any(isinstance(h, logging.FileHandler) for h in root.handlers)
        log_text = (tmp_path / "app.log").read_text(encoding="utf-8")
        assert "hello" in log_text
