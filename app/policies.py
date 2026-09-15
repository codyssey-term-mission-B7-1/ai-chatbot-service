"""코드 상수(불변 정책) — 환경과 무관한 규칙의 단일 위치."""

MAX_PASSWORD_BYTES = 72
MAX_PASSWORD_CHARS = 64
MIN_PASSWORD_CHARS = 8
MAX_NICKNAME_CHARS = 20
MAX_EMAIL_LOCAL_CHARS = 64
MAX_CONTEXT_TURNS = 200
QUESTION_ABS_MAX_CHARS = 100_000  # 질문 길이 절대 상한 — 환경값 상한(config le)과 DB CHECK가 공유
MAX_LOG_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50
ADMIN_LOG_KEEP_ROWS = 5000  # 관리자 콘솔 이벤트·네트워크 로그 보존 한도(무한 증가 방지)
MAX_AUDIT_REASON_CHARS = 200
MAX_THREAD_TITLE_CHARS = 20
DEFAULT_THREAD_TITLE = "기본 대화"
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
DEMO_EMAILS = frozenset({"demo@demo.com", "tester@demo.com", "admin@demo.com"})
REQUEST_ID_CHARS = 20
RATE_WINDOW_SECONDS = 60.0

DOCS_PATHS = frozenset({"/docs", "/docs/", "/redoc", "/redoc/", "/openapi.json"})
STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
