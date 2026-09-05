"""공통 의존성 — 인증 가드 (의존성 주입 형태라 테스트 override 가능)."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """세션 기반 접근 제어: 로그인하지 않은 사용자는 401."""
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="로그인이 필요한 기능이에요.")

    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="로그인이 필요한 기능이에요.")
    return user
