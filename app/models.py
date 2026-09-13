"""DB 모델 — users / threads / chat_logs."""

import time
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


class Thread(Base):
    """대화 스레드 — "새 채팅"으로 대화를 나눈다.

    AI 문맥은 스레드 기준으로 스코핑되며(스레드 내 직전 N개 성공 Q/A), 삭제 단위도
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

    user: Mapped[User] = relationship(back_populates="threads")
    chat_logs: Mapped[list["ChatLog"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )  # SQL 레벨 cascade (#51)
    thread_id: Mapped[int | None] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"), index=True, nullable=True
    )  # 스레드 단위 대화 — NULL은 마이그레이션 이전 레거시 기록(기본 대화로 귀속)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="success")  # success | ai_error
    request_id: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    user: Mapped[User] = relationship(back_populates="chat_logs")
    thread: Mapped[Thread | None] = relationship(back_populates="chat_logs")


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
