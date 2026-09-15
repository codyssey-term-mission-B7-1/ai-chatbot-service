"""채팅 비즈니스 로직 — 대화 저장 및 감사 로깅 계층."""

import logging

from sqlalchemy.orm import Session

from app.audit import E
from app.enums import ChatStatus
from app.logging_config import log_event
from app.repositories import chat_logs

logger = logging.getLogger("app.chat")


def save_chat_attempt(
    db: Session,
    user_id: int,
    question: str,
    answer: str,
    latency_ms: int,
    status_: ChatStatus,
    request_id: str,
    thread_id: int | None = None,
) -> int | None:
    """저장 실패 시 원문/SQL 파라미터 없이 진단 메타데이터만 기록한다."""
    try:
        row = chat_logs.save_log(
            db,
            user_id=user_id,
            question=question,
            answer=answer,
            latency_ms=latency_ms,
            status=status_,
            request_id=request_id,
            thread_id=thread_id,
        )
        log_event(
            logger,
            E.DB_SAVE_SUCCESS,
            user_id=user_id,
            chat_id=row.id,
            status=status_,
            request_id=request_id,
        )
        return row.id
    except Exception as exc:
        log_event(
            logger,
            E.DB_SAVE_FAIL,
            user_id=user_id,
            reason=type(exc).__name__,
            request_id=request_id,
            level=logging.ERROR,
        )
        return None
