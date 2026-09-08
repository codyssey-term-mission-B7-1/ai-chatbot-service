"""사용자 DB 조회·생성. 중복의 경쟁 조건도 일관된 도메인 오류로 변환한다."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User


class DuplicateEmailError(Exception):
    """이미 등록된 이메일."""


def find_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, *, email: str, password_hash: str, nickname: str) -> User:
    if find_by_email(db, email) is not None:
        raise DuplicateEmailError()
    user = User(email=email, password_hash=password_hash, nickname=nickname)
    try:
        db.add(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        if find_by_email(db, email) is not None:
            raise DuplicateEmailError() from None
        raise
    return user
