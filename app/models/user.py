"""사용자 모델 — 가입 계정과 비밀번호 해시."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import utcnow

if TYPE_CHECKING:
    from app.models.chat_log import ChatLog
    from app.models.thread import Thread


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    chat_logs: Mapped[list["ChatLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    threads: Mapped[list["Thread"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
