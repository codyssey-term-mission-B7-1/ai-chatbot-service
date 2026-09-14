"""대화 스레드 모델 — "새 채팅"으로 대화를 나누는 단위."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import utcnow

if TYPE_CHECKING:
    from app.models.chat_log import ChatLog
    from app.models.user import User


class Thread(Base):
    """대화 스레드 — "새 채팅"으로 대화를 나눈다.

    AI 문맥은 스레드 기준으로 스코핑되며(스레드 내 직전 N개 성공 Q/A), 삭제 단도도
    스레드다(기록 전체 삭제는 스레드 삭제의 특수한 경우). title은 첫 질문에서
    자동 생성되며, NULL이면 UI/API가 '기본 대화'로 표시한다.
    """

    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="threads")
    chat_logs: Mapped[list["ChatLog"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )
