"""표준 이벤트 카탈로그 — 로그 이벤트 이름의 단일 소스(Single Source of Truth)(#151)."""


class E:
    """표준 이벤트 이름 상수 — 값은 logging_config의 이벤트 이름 규칙을 따른다."""

    REQUEST_RECEIVED = "request_received"
    REQUEST_FINISHED = "request_finished"
    UNHANDLED_ERROR = "unhandled_error"

    AI_CALL_START = "ai_call_start"
    AI_CALL_SUCCESS = "ai_call_success"
    AI_CALL_FAIL = "ai_call_fail"
    AI_RETRY = "ai_retry"
    CHAT_RATE_LIMITED = "chat_rate_limited"
    DB_SAVE_SUCCESS = "db_save_success"
    DB_SAVE_FAIL = "db_save_fail"

    AUTH_STALE_SESSION = "auth_stale_session"
    AUTH_SESSION_REVOKED = "auth_session_revoked"
    USER_SIGNUP = "user_signup"
    USER_LOGIN = "user_login"
    USER_LOGIN_FAIL = "user_login_fail"
    USER_LOGIN_LOCKED = "user_login_locked"
    SIGNUP_RATE_LIMITED = "signup_rate_limited"
    AUTH_PASSWORD_REHASHED = "auth_password_rehashed"

    AUTH_PASSWORD_RESET_REQUESTED = "auth_password_reset_requested"
    AUTH_PASSWORD_RESET_RATE_LIMITED = "auth_password_reset_rate_limited"
    AUTH_PASSWORD_RESET_IP_RATE_LIMITED = "auth_password_reset_ip_rate_limited"
    AUTH_PASSWORD_RESET_EMAIL_SENT = "auth_password_reset_email_sent"
    AUTH_PASSWORD_RESET_EMAIL_DEV_CONSOLE = "auth_password_reset_email_dev_console"
    AUTH_PASSWORD_RESET_EMAIL_UNCONFIGURED = "auth_password_reset_email_unconfigured"
    AUTH_PASSWORD_RESET_EMAIL_FAILED = "auth_password_reset_email_failed"
    AUTH_PASSWORD_RESET_REJECTED = "auth_password_reset_rejected"
    AUTH_PASSWORD_RESET_COMPLETED = "auth_password_reset_completed"

    ADMIN_LOGS_VIEWED = "admin_logs_viewed"
    ADMIN_STATS_VIEWED = "admin_stats_viewed"
    ADMIN_EVENTS_VIEWED = "admin_events_viewed"
    ADMIN_NETWORK_VIEWED = "admin_network_viewed"
    ADMIN_DB_VIEWED = "admin_db_viewed"
    ADMIN_HASH_STATUS_VIEWED = "admin_hash_status_viewed"
    ADMIN_USER_DELETED = "admin_user_deleted"

    THREAD_CREATED = "thread_created"
    THREAD_DELETED = "thread_deleted"

    READYZ_DB_FAILURE = "readyz_db_failure"
    READYZ_SCHEMA_FAILURE = "readyz_schema_failure"


ALL_EVENTS = frozenset(value for key, value in vars(E).items() if key.isupper())
