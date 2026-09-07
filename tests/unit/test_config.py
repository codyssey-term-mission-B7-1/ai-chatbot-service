"""단위 테스트 — 설정 기본값 회귀 방지 (#41)."""

from app.config import Settings


def test_ai_timeout_default_is_45s(monkeypatch):
    """AI 타임아웃 기본값 45초 (env 미설정 시)."""
    monkeypatch.delenv("AI_TIMEOUT_SEC", raising=False)
    assert Settings().ai_timeout_sec == 45.0
