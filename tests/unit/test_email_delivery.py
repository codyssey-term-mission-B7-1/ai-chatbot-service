"""이메일 발송 수단 선택 — Resend 우선·SMTP 폴백·미설정 동작(단위).

배경(#12): Railway Free/Hobby는 아웃바운드 SMTP 포트(25/465/587/2525)를 차단한다
(Pro만 허용). Resend HTTPS API(443)는 항상 허용되므로 운영 기본 발송 수단이 된다.
"""

import httpx
import pytest

from app.config import settings
from app.services import password_reset as svc
from app.services.password_reset import SmtpNotConfigured

LINK = "https://app.example.test/reset-password?token=abc"
SUBJECT = "AI Chatbot Service — 비밀번호 재설정 안내"


@pytest.fixture()
def clean_delivery(monkeypatch):
    """발송 수단 설정을 전부 비운 상태에서 시작한다."""
    monkeypatch.setattr(settings, "resend_api_key", "", raising=False)
    monkeypatch.setattr(settings, "smtp_host", "", raising=False)
    return monkeypatch


def test_resend_key_sends_https_api(clean_delivery, monkeypatch):
    calls = {}

    def fake_post(url, *, headers, json, timeout):
        calls.update(url=url, headers=headers, json=json, timeout=timeout)
        return httpx.Response(200)

    monkeypatch.setattr(settings, "resend_api_key", "re_test_key", raising=False)
    monkeypatch.setattr(svc.httpx, "post", fake_post)

    assert svc.deliver_reset_email("user@example.test", LINK) == "sent"
    assert calls["url"] == "https://api.resend.com/emails"
    assert calls["headers"]["Authorization"].startswith("Bearer ")
    assert calls["json"]["to"] == ["user@example.test"]
    assert calls["json"]["subject"] == SUBJECT
    assert LINK in calls["json"]["text"]


def test_resend_takes_priority_over_smtp(clean_delivery, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key", raising=False)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test", raising=False)

    def not_smtp(*args, **kwargs):
        raise AssertionError("resend_api_key가 설정되면 SMTP로 보내지 않는다")

    monkeypatch.setattr(svc.httpx, "post", lambda url, **kwargs: httpx.Response(200))
    monkeypatch.setattr(svc.smtplib, "SMTP", not_smtp)
    monkeypatch.setattr(svc.smtplib, "SMTP_SSL", not_smtp)

    assert svc.deliver_reset_email("user@example.test", LINK) == "sent"


def test_resend_http_error_raises_without_leaking_key(clean_delivery, monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key", raising=False)
    monkeypatch.setattr(svc.httpx, "post", lambda url, **kwargs: httpx.Response(422))

    with pytest.raises(RuntimeError, match="422"):
        svc.deliver_reset_email("user@example.test", LINK)


def test_smtp_still_works_without_resend(clean_delivery, monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"], sent["port"] = host, port

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def send_message(self, message):
            sent["message"] = message

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test", raising=False)
    monkeypatch.setattr(svc.smtplib, "SMTP", FakeSMTP)

    assert svc.deliver_reset_email("user@example.test", LINK) == "sent"
    assert sent["host"] == "smtp.example.test"
    assert sent["port"] == 587  # 기본 STARTTLS
    assert sent["message"]["Subject"] == SUBJECT
    assert LINK in sent["message"].get_content()


def test_debug_without_provider_returns_dev_console(clean_delivery, monkeypatch):
    monkeypatch.setattr(settings, "debug", True, raising=False)
    assert svc.deliver_reset_email("user@example.test", LINK) == "dev_console"


def test_production_without_provider_raises(clean_delivery, monkeypatch):
    monkeypatch.setattr(settings, "debug", False, raising=False)
    with pytest.raises(SmtpNotConfigured):
        svc.deliver_reset_email("user@example.test", LINK)


def test_cd_syncs_resend_secrets_and_clears_when_absent():
    """CD 계약 — RESEND_* 를 Secrets→Railway로 동기화하고, 없으면 명시적으로 비운다."""
    from pathlib import Path

    cd = (Path(__file__).resolve().parents[2] / ".github/workflows/cd.yml").read_text()
    assert "RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}" in cd
    assert "RESEND_FROM: ${{ secrets.RESEND_FROM }}" in cd
    assert 'set_var RESEND_API_KEY "$RESEND_API_KEY" ""' in cd
    assert 'set_var RESEND_FROM "$RESEND_FROM" "onboarding@resend.dev"' in cd
