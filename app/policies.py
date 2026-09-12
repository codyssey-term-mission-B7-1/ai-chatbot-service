"""공유 입력·보안 정책. 문자 수는 Unicode 코드 포인트 기준."""

MAX_PASSWORD_BYTES = 72  # bcrypt 입력 한계; 비밀번호를 조용히 자르지 않는다.
MAX_PASSWORD_CHARS = 64
MIN_PASSWORD_CHARS = 8
MAX_NICKNAME_CHARS = 20
# RFC 5321: 로컬파트 최대 64옥텟. 너무 긴 로컬파트는 공급자도 대부분 거절한다.
MAX_EMAIL_LOCAL_CHARS = 64
MAX_CONTEXT_TURNS = 200
MAX_LOG_PAGE_SIZE = 200
# XSS 2차 방어선(#75). 인라인 script/핸들러를 쓰지 않는 전제 — 외부 파일 스크립트만 허용.
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
    # HTTPS 종단(Railway 엣지) 이후 브라우저가 HTTP 다운그레이드를 금지하도록 강제(B-6).
    # http(로컬)에선 브라우저가 무시하므로 무해하다.
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    # 이 서비스가 쓰지 않는 브라우저 기능(카메라·마이크·위치)을 명시적으로 차단.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
DEMO_EMAILS = frozenset({"demo@demo.com", "tester@demo.com", "admin@demo.com"})
