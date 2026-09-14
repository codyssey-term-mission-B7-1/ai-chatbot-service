"""비밀번호 재설정 토큰 모델."""

import time

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PasswordReset(Base):
    """이메일 기반 비밀번호 재설정 토큰 — 원문 토큰은 저장하지 않고 SHA-256 해시만 보관.

    시각은 epoch 초 정수로 저장한다(#74 SessionRevocation와 동일 방식) — SQLite가
    시간대를 왕복 보존하지 않아 naive/aware 비교 오류를 원천 차단한다.
    단일 사용(used_epoch)·만료(expires_epoch)·요청 상한(created_epoch 창)으로
    재설정 링크 남용을 제한한다. 신규 테이블이라 create_all이 기존 DB에 안전하게 추가된다.
    """

    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    used_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_epoch: Mapped[int] = mapped_column(
        Integer, default=lambda: int(time.time()), index=True
    )
    request_ip: Mapped[str] = mapped_column(String(64), default="", nullable=False)
