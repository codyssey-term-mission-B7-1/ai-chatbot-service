"""공통 의존성 — 인증 가드 (의존성 주입 형태라 테스트 override 가능)."""
import logging

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.logging_config import log_event
from app.services.security import email_fingerprint
from app.models import User

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
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """세션 기반 접근 제어: 로그인하지 않은 사용자는 401."""
    user = resolve_session_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요한 기능이에요.")
    return user
