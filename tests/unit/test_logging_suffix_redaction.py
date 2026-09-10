"""로깅 보안 계약 강화 — 접미사 마스킹·필드명 규칙 회귀 테스트.

app/logging_config.log_event 의 두 보호 계약을 고정한다:
1) SENSITIVE_FIELDS 정확 일치 외에도, 키 이름이 `_secret`/`_token` 로 끝나면
   값이 `[REDACTED]` 로 마스킹되어 원문이 로그에 새지 않는다.
2) 로그 필드명은 `[a-z][a-z0-9_]*` 만 허용되며, 규칙 위반 시 즉시 ValueError.

이 계약을 지킴으로써 추후 어떤 로그 필드가 추가돼도 "이름만 비슷하면 원문 노출"을
구조적으로 막는다. 실제 작성/검토 후 담당 계정으로 커밋한다.
"""

import logging

import pytest

from app.logging_config import log_event


def test_suffix_keys_are_redacted_even_when_not_in_sensitive_set(caplog):
    """SENSITIVE_FIELDS 에 없는 키라도 `_secret`/`_token` 접미사면 마스킹된다."""
    with caplog.at_level(logging.INFO):
        log_event(
            logging.getLogger("app.test"),
            "db_save_fail",
            provider_secret="super-secret-value",
            reset_token="token-abc-123",
            attempt=1,
        )
    message = caplog.records[-1].getMessage()
    # 접미사 보호 필드는 원문이 아니라 [REDACTED]
    assert "super-secret-value" not in message
    assert "token-abc-123" not in message
    assert message.count("[REDACTED]") == 2
    # 그 외 정상 메타데이터는 남는다
    assert "attempt=1" in message


def test_non_sensitive_metadata_is_not_redacted(caplog):
    """접미사/민감집합 밖의 정상 메타데이터는 그대로 로깅된다."""
    with caplog.at_level(logging.INFO):
        log_event(
            logging.getLogger("app.test"),
            "ai_call_fail",
            status_code=504,
            latency_ms=45210,
        )
    message = caplog.records[-1].getMessage()
    assert "status_code=504" in message
    assert "latency_ms=45210" in message
    assert "[REDACTED]" not in message


def test_invalid_field_name_is_rejected():
    """로그 필드명은 소문자 시작 + 소문자/숫자/밑줄만. 대문자·하이픈은 거부."""
    logger = logging.getLogger("app.test")
    with pytest.raises(ValueError, match="Invalid log field name"):
        log_event(logger, "user_login", BadField="value")
    with pytest.raises(ValueError, match="Invalid log field name"):
        log_event(logger, "user_login", **{"dashed-key": "value"})


def test_empty_and_padded_values_log_safely(caplog):
    """값이 없거나 공백만 있어도 이벤트는 성공하고 예외가 나지 않는다."""
    with caplog.at_level(logging.INFO):
        log_event(logging.getLogger("app.test"), "db_save_success", user_id=None, rows=0)
    message = caplog.records[-1].getMessage()
    assert "event=db_save_success" in message
    assert "user_id=-" in message
