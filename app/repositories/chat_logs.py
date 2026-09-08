"""대화 기록 조회·저장. UI 복원과 AI 문맥은 동일한 성공 대화 조회 함수를 사용한다."""

from sqlalchemy.orm import Session

from app.models import ChatLog
from app.policies import MAX_LOG_PAGE_SIZE


def list_logs(
    db: Session,
    *,
    user_id: int | None,
    limit: int = 50,
    status: str | None = None,
    before_id: int | None = None,
) -> list[ChatLog]:
    query = db.query(ChatLog)
    if user_id is not None:
        query = query.filter(ChatLog.user_id == user_id)
    if status is not None:
        query = query.filter(ChatLog.status == status)
    if before_id is not None:
        query = query.filter(ChatLog.id < before_id)
    return query.order_by(ChatLog.id.desc()).limit(max(1, min(limit, MAX_LOG_PAGE_SIZE))).all()


def successful_context(db: Session, user_id: int, turns: int) -> list[ChatLog]:
    if turns <= 0:
        return []
    return list_logs(db, user_id=user_id, status="success", limit=turns)[::-1]


def save_log(
    db: Session,
    *,
    user_id: int,
    question: str,
    answer: str,
    latency_ms: int,
    status: str,
    request_id: str,
) -> ChatLog:
    row = ChatLog(
        user_id=user_id,
        question=question,
        answer=answer,
        latency_ms=latency_ms,
        status=status,
        request_id=request_id,
    )
    try:
        db.add(row)
        db.commit()
        return row
    except Exception:
        db.rollback()
        raise
