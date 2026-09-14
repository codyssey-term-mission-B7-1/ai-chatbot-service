"""HTTP 미들웨어 패키지 — 등록 순서까지 한곳에서 관리한다(#150).

Starlette은 마지막에 등록한 미들웨어가 가장 바깥에서 실행된다. 따라서 실행 순서는
(바깥) Session → log_requests → request_guard → body_size_guard → security_headers (안).
순서를 바꿀 때는 docs/LOGGING.md 로그 계약과 관련 테스트를 반드시 함께 확인한다.

공용 상수(DOCS_PATHS·STATE_CHANGING_METHODS)는 app/policies.py에 둔다 —
미들웨어와 정책이 같은 값을 따로 정의하지 않게.
"""

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.middleware import body_size, request_guard, request_logging, security_headers


def register(app: FastAPI) -> None:
    """main.py가 호출하는 유일한 진입점 — 등록 순서가 곧 실행 순서의 역순이다."""
    app.middleware("http")(security_headers.security_headers)
    app.middleware("http")(body_size.body_size_guard)
    app.middleware("http")(request_guard.request_guard)
    app.middleware("http")(request_logging.log_requests)
    # 가장 바깥 미들웨어 — 세션 쿠키는 서명만 하며 암호화하지 않는다.
    # 쿠키에는 user_id/email_fp만 넣는다. 기본 24시간(#74).
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        max_age=settings.session_max_age_hours * 3600,  # 기본 24시간(#74)
        https_only=not settings.debug,
    )
