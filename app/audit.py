"""표준 이벤트 카탈로그 — 로그 이벤트 이름의 단일 소스(Single Source of Truth)(#151).

log_event는 정의되지 않은 이벤트를 ValueError로 거부한다. 이벤트 이름 문자열을
여기서만 정의하고 호출부는 `E.*` 상수를 쓰게 해, 오타를 런타임 오류가 아니라
import 시점 오류로 바꾼다.

역할 경계(#150):
- 이 모듈(audit)  = **무엇을** 기록할지 — 이벤트 카탈로그
- logging_config  = **어떻게** 기록할지 — 포맷·마스킹·request_id 주입·출력

이벤트 추가 절차: ① 여기에 상수를 추가한다 ② docs/LOGGING.md의 이벤트 표를
갱신한다 ③ 새 이벤트를 기록하는 코드와 함께 회귀 테스트를 넣는다.
이벤트를 없앨 때는 호출부가 남아 있으면 tests/unit/test_audit.py가 잡아준다.
"""


class E:
    """표준 이벤트 이름 상수 — 값은 logging_config의 이벤트 이름 규칙을 따른다."""

    # ── 요청 수명 ──────────────────────────────────────────────
    REQUEST_RECEIVED = "request_received"
    REQUEST_FINISHED = "request_finished"
    UNHANDLED_ERROR = "unhandled_error"

    # ── 채팅 파이프라인 ────────────────────────────────────────
    AI_CALL_START = "ai_call_start"
    AI_CALL_SUCCESS = "ai_call_success"
    AI_CALL_FAIL = "ai_call_fail"
    AI_RETRY = "ai_retry"
    CHAT_RATE_LIMITED = "chat_rate_limited"
    DB_SAVE_SUCCESS = "db_save_success"
    DB_SAVE_FAIL = "db_save_fail"

    # ── 인증/세션 ─────────────────────────────────────────────
    AUTH_STALE_SESSION = "auth_stale_session"
    AUTH_SESSION_REVOKED = "auth_session_revoked"
    USER_SIGNUP = "user_signup"
    USER_LOGIN = "user_login"
    USER_LOGIN_FAIL = "user_login_fail"
    USER_LOGIN_LOCKED = "user_login_locked"
    SIGNUP_RATE_LIMITED = "signup_rate_limited"
    AUTH_PASSWORD_REHASHED = "auth_password_rehashed"

    # ── 비밀번호 재설정 ────────────────────────────────────────
    AUTH_PASSWORD_RESET_REQUESTED = "auth_password_reset_requested"
    AUTH_PASSWORD_RESET_RATE_LIMITED = "auth_password_reset_rate_limited"
    AUTH_PASSWORD_RESET_IP_RATE_LIMITED = "auth_password_reset_ip_rate_limited"
    AUTH_PASSWORD_RESET_EMAIL_SENT = "auth_password_reset_email_sent"
    AUTH_PASSWORD_RESET_EMAIL_DEV_CONSOLE = "auth_password_reset_email_dev_console"
    AUTH_PASSWORD_RESET_EMAIL_UNCONFIGURED = "auth_password_reset_email_unconfigured"
    AUTH_PASSWORD_RESET_EMAIL_FAILED = "auth_password_reset_email_failed"
    AUTH_PASSWORD_RESET_REJECTED = "auth_password_reset_rejected"
    AUTH_PASSWORD_RESET_COMPLETED = "auth_password_reset_completed"

    # ── 관리자 ────────────────────────────────────────────────
    ADMIN_LOGS_VIEWED = "admin_logs_viewed"
    ADMIN_HASH_STATUS_VIEWED = "admin_hash_status_viewed"
    ADMIN_USER_DELETED = "admin_user_deleted"

    # ── 대화(스레드) ──────────────────────────────────────────
    THREAD_CREATED = "thread_created"
    THREAD_DELETED = "thread_deleted"

    # ── 운영/기동 상태 ────────────────────────────────────────
    READYZ_DB_FAILURE = "readyz_db_failure"
    READYZ_SCHEMA_FAILURE = "readyz_schema_failure"


ALL_EVENTS = frozenset(value for key, value in vars(E).items() if key.isupper())
