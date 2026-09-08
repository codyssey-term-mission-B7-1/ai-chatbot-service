"""단위 테스트 — 설정 기본값/보안 게이트 회귀 방지 (#41, SESSION_SECRET 가드)."""

import pytest

from app.config import (
    INSECURE_SECRETS,
    MIN_SECRET_LEN,
    Settings,
    load_settings,
    resolve_session_secret,
)


def test_ai_timeout_default_is_45s(monkeypatch):
    """AI 타임아웃 기본값 45초 (env 미설정 시)."""
    monkeypatch.delenv("AI_TIMEOUT_SEC", raising=False)
    assert Settings().ai_timeout_sec == 45.0


def test_strong_secret_is_used_as_is():
    good = "a" * MIN_SECRET_LEN
    assert resolve_session_secret(good, debug=False) == good


def test_insecure_default_secret_in_production_raises():
    """공개된 예시 값으로는 쿠키 위조가 가능하므로 운영에서 기동을 막는다."""
    for bad in sorted(INSECURE_SECRETS):
        with pytest.raises(RuntimeError):
            resolve_session_secret(bad, debug=False)


def test_short_secret_in_production_raises():
    with pytest.raises(RuntimeError):
        resolve_session_secret("tooshort", debug=False)


def test_insecure_secret_in_debug_is_replaced_by_random_one():
    """로컬/테스트 부팅은 깨뜨리지 않으면서 공개 값으로 서명하지 않게 대체한다."""
    first = resolve_session_secret("dev-secret-change-me", debug=True)
    assert len(first) >= MIN_SECRET_LEN
    assert first != "dev-secret-change-me"
    assert resolve_session_secret("dev-secret-change-me", debug=True) != first


def test_load_settings_wires_the_guard_in_production(monkeypatch):
    """get_settings의 설정 로딩 경로에서 시크릿 검증 함수를 실제로 호출하는지 확인한다."""
    monkeypatch.setenv("SESSION_SECRET", "change-me-to-random-string")
    monkeypatch.setenv("DEBUG", "false")
    with pytest.raises(RuntimeError):
        load_settings()


def test_load_settings_bootstraps_a_secret_in_debug(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "change-me-to-random-string")
    monkeypatch.setenv("DEBUG", "true")
    assert len(load_settings().session_secret) >= MIN_SECRET_LEN
