"""공통 의존성 — 인증 가드 (의존성 주입 형태라 테스트 override 가능)."""

import logging

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.logging_config import log_event
from app.models import User
from app.services.admin import is_admin
from app.services.security import email_fingerprint
from app.services.sessions import is_session_revoked

logger = logging.getLogger("app.auth")


def resolve_session_user(request: Request, db: Session) -> User | None:
    """API와 HTML 경로에서 공통으로 사용하는 세션 검증.

    쿠키가 현재 DB의 사용자와 일치하는지 확인한다.

    DB 재생성 등으로 id가 다른 행을 가리키게 된 stale 세션은 파기 후 None (#33).
    """
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    try:
        user = db.get(User, int(user_id))
    except (TypeError, ValueError):
        user = None
    if user is None or email_fingerprint(user.email) != request.session.get("email_fp"):
        log_event(logger, "auth_stale_session", user_id=user_id, level=logging.WARNING)
        request.session.clear()
        return None
    # 서버 측 폐기(#74): 계정별 폐기 기준 이전에 발급(iat)된 세션은 거부한다.
    # 구버전 쿠키(iat 없음)는 0으로 취급해 폐기 기준이 있으면 함께 무효화된다.
    iat = request.session.get("iat")
    if not isinstance(iat, int) or isinstance(iat, bool):
        iat = 0
    if is_session_revoked(db, user.id, iat):
        log_event(logger, "auth_session_revoked", user_id=user.id, level=logging.WARNING)
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
