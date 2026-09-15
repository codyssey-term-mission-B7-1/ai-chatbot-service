"""대화 로그 모델 — 질문/응답·지연·상태(AI 감사와 복원의 원천)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ChatStatus
from app.models.base import utcnow
from app.policies import REQUEST_ID_CHARS

if TYPE_CHECKING:
    from app.models.thread import Thread
    from app.models.user import User


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    thread_id: Mapped[int | None] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), index=True, nullable=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=ChatStatus.SUCCESS.value)
    request_id: Mapped[str] = mapped_column(String(REQUEST_ID_CHARS), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    user: Mapped["User"] = relationship(back_populates="chat_logs")
    thread: Mapped["Thread | None"] = relationship(back_populates="chat_logs")
