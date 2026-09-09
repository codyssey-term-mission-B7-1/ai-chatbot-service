"""서버 측 세션 폐기(#74) — 시크릿 교체 없이 특정 계정의 기존 세션을 무효화한다.

세션 쿠키는 서명만 되는 방식이라 기본적으로 서버가 개별 세션을 폐기할 수 없다.
로그인 시 쿠키에 발급 시각(iat)을 넣고, 이 값이 폐기 기준 시점 이하인 세션은
DB 대조 단계에서 거부한다. 신뢰된 서버 CLI(scripts/revoke_sessions.py)에서만 호출한다.
"""

import time

from sqlalchemy.orm import Session

from app.models import SessionRevocation, User
from app.repositories.users import find_by_email


def revoke_user_sessions(db: Session, user: User) -> int:
    """해당 계정의 '현재 시점 이전' 발급 세션을 모두 무효화한다. 반환값은 기준 epoch 초."""
    epoch = int(time.time())
    row = db.get(SessionRevocation, user.id)
    if row is None:
        db.add(SessionRevocation(user_id=user.id, revoked_before_epoch=epoch))
    else:
        row.revoked_before_epoch = epoch
    db.commit()
    return epoch


def is_session_revoked(db: Session, user_id: int, iat: int) -> bool:
    """iat가 폐기 기준 이하(같은 초 포함)면 폐기된 세션이다. 폐기 이후 재로그인은 통과한다."""
    row = db.get(SessionRevocation, user_id)
    return row is not None and iat <= row.revoked_before_epoch


def revoke_sessions_by_email(db: Session, email: str) -> User:
    """CLI 진입점 — 이메일로 계정을 찾아 세션을 폐기한다. 없으면 ValueError."""
    user = find_by_email(db, email.strip().lower())
    if user is None:
        raise ValueError("존재하지 않는 이메일입니다. 먼저 회원가입으로 계정을 만드세요.")
    revoke_user_sessions(db, user)
    return user
