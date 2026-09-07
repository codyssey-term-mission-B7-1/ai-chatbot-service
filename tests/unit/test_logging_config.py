"""단위 테스트 — 로그 유틸 (포맷·민감정보 정책 회귀 방지, #11)."""
import logging

from app.logging_config import log_event, truncate


def test_truncate_short_text_unchanged():
    assert truncate("짧은 질문") == "짧은 질문"


def test_truncate_boundary_50_chars_unchanged():
    assert truncate("가" * 50) == "가" * 50


def test_truncate_long_text_cut_with_ellipsis():
    assert truncate("가" * 51) == "가" * 50 + "…"


def test_log_event_format(caplog):
    """event=<이름> key=value 형식 + request_id 포함."""
    logger = logging.getLogger("test.tracing")
    with caplog.at_level(logging.INFO, logger="test.tracing"):
        log_event(logger, "ai_call_start", user_id=7, request_id="abc123")
    assert "event=ai_call_start user_id=7 request_id=abc123" in caplog.text


def test_log_event_error_level(caplog):
    logger = logging.getLogger("test.tracing")
    with caplog.at_level(logging.ERROR, logger="test.tracing"):
        log_event(logger, "ai_call_fail", request_id="abc123", reason="timeout",
                  level=logging.ERROR)
    assert "event=ai_call_fail" in caplog.text
    assert "reason=timeout" in caplog.text
