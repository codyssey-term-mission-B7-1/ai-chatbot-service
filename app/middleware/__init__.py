"""HTTP 미들웨어 패키지 — 등록 순서까지 한곳에서 관리한다(#150)."""

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
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        max_age=settings.session_max_age_hours * 3600,
        https_only=not settings.debug,
    )
