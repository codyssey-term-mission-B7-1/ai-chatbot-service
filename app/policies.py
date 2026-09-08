"""공유 입력·보안 정책. 문자 수는 Unicode 코드 포인트 기준."""

MAX_PASSWORD_BYTES = 72  # bcrypt 입력 한계; 비밀번호를 조용히 자르지 않는다.
MAX_PASSWORD_CHARS = 64
MIN_PASSWORD_CHARS = 8
MAX_NICKNAME_CHARS = 20
MAX_CONTEXT_TURNS = 200
MAX_LOG_PAGE_SIZE = 200
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}
DEMO_EMAILS = frozenset({"demo@demo.com", "tester@demo.com", "admin@demo.com"})
