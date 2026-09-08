"""한 줄 로그·민감 필드 보호·이벤트 등록 계약."""

import logging

import pytest

from app.logging_config import log_event


def test_log_values_escape_newlines_and_do_not_echo_sensitive_fields(caplog):
    with caplog.at_level(logging.INFO):
        log_event(
            logging.getLogger("app.test"),
            "db_save_fail",
            reason="첫째 줄\n둘째 줄",
            question="private question",
            api_key="private key",
            password="private password",
        )
    message = caplog.records[-1].getMessage()
    assert "\n" not in message and "\\n" in message
    assert "private" not in message and "[REDACTED]" in message


def test_unknown_event_is_rejected():
    with pytest.raises(ValueError, match="Unregistered"):
        log_event(logging.getLogger("app.test"), "unknown_event")
