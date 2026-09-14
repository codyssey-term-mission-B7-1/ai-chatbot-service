"""세션·관리자 권한 모델 — 서버 측 폐기 기준과 명시적 권한 부여."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import utcnow


class SessionRevocation(Base):
    """서버 측 세션 폐기 기준(#74) — iat가 이 값 이하로 발급된 세션은 서명이 유효해도 거부.

    신규 테이블이라 create_all이 기존 DB에 안전하게 추가한다(기존 열 변경 없음).
    """

    __tablename__ = "session_revocations"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    revoked_before_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdminGrant(Base):
    """운영자가 명시적으로 부여한 앱 관리자 권한. 기존 users 열 변경 없이 별도 테이블 사용."""

    __tablename__ = "admin_grants"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    granted_email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
