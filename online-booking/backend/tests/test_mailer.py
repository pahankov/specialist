"""Tests for app.services.mailer — SMTP is faked, no network."""
from email.header import decode_header, make_header

import pytest

from app.config import settings
from app.services import mailer


def _decoded(value) -> str:
    """RFC2047-decode a header value (formataddr encodes Cyrillic)."""
    return str(make_header(decode_header(str(value))))


class FakeSSL:
    """Minimal stand-in for smtplib.SMTP_SSL (context manager)."""

    instances: list = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host = host
        self.port = port
        self.login_args = None
        self.messages = []
        FakeSSL.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, msg):
        self.messages.append(msg)


@pytest.fixture
def smtp_conf(monkeypatch):
    FakeSSL.instances = []
    monkeypatch.setattr(settings, "SMTP_USER", "beauty-specialist@yandex.ru")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "app-password")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "")
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSSL)
    return FakeSSL


async def test_send_email_disabled_logs_only(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    def boom(*args, **kwargs):
        raise AssertionError("SMTP must not be touched when disabled")

    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", boom)

    assert await mailer.send_email("client@mail.ru", "Тема", "Текст") is False


async def test_send_email_empty_recipient(smtp_conf):
    assert await mailer.send_email("   ", "Тема", "Текст") is False
    assert FakeSSL.instances == []


async def test_send_email_happy_path(smtp_conf):
    ok = await mailer.send_email("client@mail.ru", "Тема письма",
                                 "Первая строка")
    assert ok is True
    assert len(FakeSSL.instances) == 1
    inst = FakeSSL.instances[0]
    assert (inst.host, inst.port) == ("smtp.yandex.ru", 465)
    assert inst.login_args == ("beauty-specialist@yandex.ru", "app-password")

    msg = inst.messages[0]
    assert msg["To"] == "client@mail.ru"
    assert "Электронная запись" in _decoded(msg["From"])
    assert "beauty-specialist@yandex.ru" in str(msg["From"])

    body = msg.get_content()
    assert "Первая строка" in body
    assert "Электронная запись · beauty-specialist.ru" in body
    assert "отвечать на него не нужно" in body


async def test_send_email_smtp_failure_is_swallowed(smtp_conf, monkeypatch):
    class Broken(FakeSSL):
        def login(self, user, password):
            raise OSError("connection reset")

    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", Broken)
    assert await mailer.send_email("client@mail.ru", "Тема", "Текст") is False


async def test_password_reset_code_email(smtp_conf):
    ok = await mailer.send_password_reset_code("client@mail.ru", "482913")
    assert ok is True
    msg = FakeSSL.instances[0].messages[0]
    assert "парол" in _decoded(msg["Subject"]).lower()
    body = msg.get_content()
    assert "482913" in body
    assert f"{mailer.EMAIL_CODE_TTL_MINUTES} минут" in body
    assert "beauty-specialist.ru" in body


async def test_email_confirm_code_email(smtp_conf):
    ok = await mailer.send_email_confirm_code("new@mail.ru", "000111")
    assert ok is True
    msg = FakeSSL.instances[0].messages[0]
    assert "подтвержд" in _decoded(msg["Subject"]).lower()
    body = msg.get_content()
    assert "000111" in body
    assert "new@mail.ru" in body


def test_with_signature_appends_once():
    body = mailer.with_signature("Привет")
    assert body.startswith("Привет\n\n—\n")
    assert body.count("Письмо отправлено автоматически") == 1
