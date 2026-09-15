"""코드 상수(불변 정책) — 환경과 무관한 보안·도메인·인프라 불변식의 단일 원천(#152).

이 파일의 값들은 배포 환경(.env)에 따라 임의로 완화되어서는 안 되는 보안 및 프로토콜 규격입니다.
환경에 따라 변경 가능한 튜닝 수치는 app/config.py의 Settings에 정의됩니다.
"""

# ==============================================================================
# 1. 암호학적 및 인증 보안 불변 정책 (Cryptographic & Auth Security Invariants)
# ==============================================================================
MAX_PASSWORD_BYTES = 72  # bcrypt 알고리즘의 최대 바이트 한계 (초과 시 잘림 취약점 방지)
REQUEST_ID_CHARS = 20  # 분산 추적용 UUID 절단 길이 (발급/DB 컬럼 공통)
# 관리자 승격 절대 금지 계정 (공개 데모 패스워드 사용)
DEMO_EMAILS = frozenset({"demo@demo.com", "tester@demo.com", "admin@demo.com"})

# ==============================================================================
# 2. 도메인 데이터 검증 규칙 (Domain Validation Rules)
# ==============================================================================
MIN_PASSWORD_CHARS = 8  # 비밀번호 최소 길이
MAX_PASSWORD_CHARS = 64  # 비밀번호 최대 길이
MAX_NICKNAME_CHARS = 20  # 사용자 닉네임 최대 길이
MAX_EMAIL_LOCAL_CHARS = 64  # 이메일 로컬파트(@ 앞부분) 최대 길이
MAX_THREAD_TITLE_CHARS = 20  # 대화 스레드 제목 최대 길이
DEFAULT_THREAD_TITLE = "기본 대화"  # 제목 미지정 스레드의 기본 표시명

# ==============================================================================
# 3. 시스템 안전 한계 절대 상한선 (System Safety Ceilings)
# ==============================================================================
# 환경설정(Settings)으로 조절할 수 있으나, 시스템 안정성을 위해 절대 넘을 수 없는 상한
MAX_CONTEXT_TURNS = 200  # AI 대화 문맥 턴 절대 상한선
QUESTION_ABS_MAX_CHARS = 100_000  # 질문 길이 절대 상한 (DB CHECK 제약과 공유)
MAX_LOG_PAGE_SIZE = 200  # API/관리자 콘솔 페이지네이션 요청 최대 상한 (DoS 방어)
MAX_AUDIT_REASON_CHARS = 200  # 관리자 로그 열람 사유 최대 길이

# ==============================================================================
# 4. 웹 보안 헤더 및 HTTP 인프라 정책 (Web Security & HTTP Infrastructure)
# ==============================================================================
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
DOCS_PATHS = frozenset({"/docs", "/docs/", "/redoc", "/redoc/", "/openapi.json"})
STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# ==============================================================================
# 5. 운영 기본값 상수 (Operational Defaults)
# ==============================================================================
DEFAULT_PAGE_SIZE = 50  # 목록 조회 기본 페이징 크기
RATE_WINDOW_SECONDS = 60.0  # 분당 요청 레이트 리미트 기본 윈도우(초)
ADMIN_LOG_KEEP_ROWS = 5000  # 감사/네트워크 로그 기본 보존 행수
