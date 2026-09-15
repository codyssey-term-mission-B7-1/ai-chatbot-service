"""비밀번호 재설정 토큰 모델."""

import time

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PasswordReset(Base):
    """이메일 기반 비밀번호 재설정 토큰 — 원문 토큰은 저장하지 않고 SHA-256 해시만 보관."""

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
