"""대화 스레드(새 채팅) — 생성·목록·기본 대화 해제·삭제."""

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import ChatLog, Thread, utcnow
from app.policies import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_THREAD_TITLE,
    MAX_LOG_PAGE_SIZE,
    MAX_THREAD_TITLE_CHARS,
)


def _truncate_title(question: str) -> str:
    """코드포인트 기준(리스트 분해 — surrogate pair 안전) — policies의 문자 수 계약과 동일."""
    s = " ".join(question.split())
    return "".join(list(s)[:MAX_THREAD_TITLE_CHARS])


def create_thread(db: Session, *, user_id: int) -> Thread:
    thread = Thread(user_id=user_id, title=None)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def get_thread(db: Session, thread_id: int, *, user_id: int | None = None) -> Thread | None:
    query = db.query(Thread).filter(Thread.id == thread_id)
    if user_id is not None:
        query = query.filter(Thread.user_id == user_id)
    return query.first()


def list_threads(db: Session, *, user_id: int, limit: int = DEFAULT_PAGE_SIZE) -> list[Thread]:
    """최근 활동순(updated_at desc, id desc) — '나중에 보러올' 스레드가 위쪽에 온다."""
    return (
        db.query(Thread)
        .filter(Thread.user_id == user_id)
        .order_by(Thread.updated_at.desc(), Thread.id.desc())
        .limit(max(1, min(limit, MAX_LOG_PAGE_SIZE)))
        .all()
    )


def resolve_default_thread(db: Session, user_id: int) -> Thread:
    """사용자의 기본 대화(가장 오래된 스레드) 반환 — 없으면 '기본 대화'로 생성."""
    thread = db.query(Thread).filter(Thread.user_id == user_id).order_by(Thread.id.asc()).first()
    if thread is not None:
        return thread
    thread = Thread(user_id=user_id, title=DEFAULT_THREAD_TITLE)
    db.add(thread)
    db.flush()
    db.execute(
        update(ChatLog)
        .where(ChatLog.user_id == user_id, ChatLog.thread_id.is_(None))
        .values(thread_id=thread.id)
    )
    db.commit()
    db.refresh(thread)
    return thread


def count_threads(db: Session, *, user_id: int) -> int:
    return db.query(Thread).filter(Thread.user_id == user_id).count()


def delete_thread(db: Session, thread_id: int) -> bool:
    thread = get_thread(db, thread_id)
    if thread is None:
        return False
    db.delete(thread)
    db.commit()
    return True


def touch_after_message(db: Session, thread_id: int, question: str) -> None:
    """메시지 저장 성공 후: 최초 메시지로 제목 자동 생성 + 활동 시각 갱신."""
    try:
        thread = get_thread(db, thread_id)
        if thread is None:
            return
        if thread.title is None:
            thread.title = _truncate_title(question) or DEFAULT_THREAD_TITLE
        thread.updated_at = utcnow()
        db.commit()
    except Exception:
        db.rollback()
