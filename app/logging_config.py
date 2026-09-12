"""표준 이벤트: stderr, 한 줄당 한 이벤트, 값은 필요 시 JSON 문자열로 이스케이프.

로그에는 질문/응답·실제 이메일·비밀번호·키·쿠키 값을 기록하지 않는다.
로그 목적·필드·집계 기준은 docs/LOGGING.md를 따른다.
"""

import json
import logging
import re
import sys
from contextvars import ContextVar

REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)
EVENTS = frozenset(
    {
        "request_received",
        "request_finished",
        "ai_call_start",
        "ai_call_success",
        "ai_call_fail",
        "chat_rate_limited",
        "ai_retry",
        "db_save_success",
        "db_save_fail",
        "unhandled_error",
        "auth_stale_session",
        "auth_session_revoked",
        "user_signup",
        "user_login",
        "user_login_fail",
        "user_login_locked",
        "signup_rate_limited",
        "admin_logs_viewed",
        "admin_hash_status_viewed",
        "admin_user_deleted",
        "auth_password_rehashed",
        "auth_password_reset_requested",
        "auth_password_reset_rate_limited",
        "auth_password_reset_ip_rate_limited",
        "auth_password_reset_email_sent",
        "auth_password_reset_email_dev_console",
        "auth_password_reset_email_unconfigured",
        "auth_password_reset_email_failed",
        "auth_password_reset_rejected",
        "auth_password_reset_completed",
    }
)
SENSITIVE_FIELDS = frozenset(
    {
        "password",
        "api_key",
        "session_secret",
        "authorization",
        "cookie",
        "token",
        "question",
        "answer",
        "email",
    }
)
SYSTEM_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9_./:@+-]+$")


def setup_logging(level: int = logging.INFO) -> None:
    """별도 로깅 설정이 없는 실행의 표준 이벤트 출력은 stderr로 명시한다."""
    logging.basicConfig(level=level, format=SYSTEM_LOG_FORMAT, stream=sys.stderr)


def _value(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, str) and _SAFE_VALUE.fullmatch(value):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields) -> None:
    """정의된 이벤트만 기록. 입력 원문 대신 길이·상태·식별자 등 허용된 메타데이터 사용."""
    if event not in EVENTS:
        raise ValueError("Unregistered log event")
    if "request_id" not in fields and REQUEST_ID.get() is not None:
        fields = {"request_id": REQUEST_ID.get(), **fields}
    parts = [f"event={event}"]
    for key, value in fields.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise ValueError("Invalid log field name")
        if key in SENSITIVE_FIELDS or key.endswith(("_secret", "_token")):
            value = "[REDACTED]"
        parts.append(f"{key}={_value(value)}")
    logger.log(level, " ".join(parts))


def truncate(text: str, limit: int = 50) -> str:
    """표시용 문자 수 제한. 개인정보 마스킹 함수가 아니며 요청 원문 로깅에는 쓰지 않는다."""
    return text if len(text) <= limit else text[:limit] + "…"
