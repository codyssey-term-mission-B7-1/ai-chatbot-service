"""앱 관리자 권한: 서버 운영자의 명시적 부여만 허용. GitHub 역할과 무관하다."""

from sqlalchemy.orm import Session

from app.models import AdminGrant, User
from app.policies import DEMO_EMAILS
from app.repositories.users import find_by_email


def is_admin(db: Session, user: User) -> bool:
    grant = db.get(AdminGrant, user.id)
    return grant is not None and grant.granted_email == user.email


def grant_admin(db: Session, email: str) -> User:
    """신뢰된 서버 CLI에서만 호출. 가입 API로는 권한을 받을 수 없다."""
    email = email.strip().lower()
    if email in DEMO_EMAILS:
        raise ValueError("공개 비밀번호를 사용하는 데모 계정에는 관리자 권한을 부여할 수 없습니다.")
    user = find_by_email(db, email)
    if user is None:
        raise ValueError("먼저 전용 관리자 계정을 회원가입으로 생성하세요.")
    grant = db.get(AdminGrant, user.id)
    if grant is None:
        db.add(AdminGrant(user_id=user.id, granted_email=user.email))
    else:
        grant.granted_email = user.email
    db.commit()
    return user


def revoke_admin(db: Session, email: str) -> bool:
    user = find_by_email(db, email.strip().lower())
    if user is None:
        return False
    grant = db.get(AdminGrant, user.id)
    if grant is None:
        return False
    db.delete(grant)
    db.commit()
    return True
