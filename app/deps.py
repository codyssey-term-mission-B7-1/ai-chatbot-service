"""공통 의존성 — 인증 가드 (의존성 주입 형태라 테스트 override 가능)."""

import logging

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit import E
from app.database import get_db
from app.logging_config import log_event
from app.models import User
from app.services.admin import is_admin
from app.services.rate_limit import (
    SlidingWindowLimiter,
    chat_limiter,
    login_limiter,
    password_reset_ip_limiter,
    signup_ip_limiter,
)
from app.services.security import email_fingerprint
from app.services.sessions import is_session_revoked

logger = logging.getLogger("app.auth")


def get_chat_limiter() -> "SlidingWindowLimiter":
    return chat_limiter


def get_login_limiter() -> "SlidingWindowLimiter":
    return login_limiter


def get_signup_ip_limiter() -> "SlidingWindowLimiter":
    return signup_ip_limiter


def get_password_reset_ip_limiter() -> "SlidingWindowLimiter":
    return password_reset_ip_limiter


def resolve_session_user(request: Request, db: Session) -> User | None:
    """API와 HTML 경로에서 공통으로 사용하는 세션 검증."""
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    try:
        user = db.get(User, int(user_id))
    except (TypeError, ValueError):
        user = None
    if user is None or email_fingerprint(user.email) != request.session.get("email_fp"):
        log_event(logger, E.AUTH_STALE_SESSION, user_id=user_id, level=logging.WARNING)
        request.session.clear()
        return None
    iat = request.session.get("iat")
    if not isinstance(iat, int) or isinstance(iat, bool):
        iat = 0
    if is_session_revoked(db, user.id, iat):
        log_event(logger, E.AUTH_SESSION_REVOKED, user_id=user.id, level=logging.WARNING)
        request.session.clear()
        return None
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """세션 기반 접근 제어: 로그인하지 않은 사용자는 401."""
    user = resolve_session_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요한 기능이에요.")
    request.state.authenticated_user_id = user.id
    return user


def get_admin_user(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    """서버에서 명시적으로 부여한 관리자 권한만 인정한다."""
    if not is_admin(db, user):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요한 기능이에요.")
    return user
