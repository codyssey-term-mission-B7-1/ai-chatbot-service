"""대화 스레드(새 채팅) — 생성·목록·기본 대화 해제·삭제.

- '기본 대화' = 사용자가 만든 가장 오래된 스레드. 없어지면 첫 채팅 시 재생성된다.
- 기존 사용자(마이그레이션)는 '기본 대화' 스레드가 이미 백필되어 있다.
- 삭제는 FK CASCADE로 그 스레드의 chat_logs도 함께 지워진다(SQLite PRAGMA
  foreign_keys=ON — app/database.py에서 모든 연결에 설정).
"""

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import ChatLog, Thread, utcnow
from app.policies import DEFAULT_THREAD_TITLE, MAX_THREAD_TITLE_CHARS


def _truncate_title(question: str) -> str:
    """코드포인트 기준(리스트 분해 — surrogate pair 안전) — policies의 문자 수 계약과 동일."""
    s = " ".join(question.split())  # 줄바꿈/중복 공백 압축 — 목록 표시용
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


def list_threads(db: Session, *, user_id: int, limit: int = 50) -> list[Thread]:
    """최근 활동순(updated_at desc, id desc) — '나중에 보러올' 스레드가 위쪽에 온다."""
    return (
        db.query(Thread)
        .filter(Thread.user_id == user_id)
        .order_by(Thread.updated_at.desc(), Thread.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )


def resolve_default_thread(db: Session, user_id: int) -> Thread:
    """사용자의 기본 대화(가장 오래된 스레드) 반환 — 없으면 '기본 대화'로 생성.

    생성 시 thread_id=NULL인 레거시 기록을 이 스레드에 귀속한다(레이지 백필) —
    운영은 alembic 마이그레이션이 이미 백필해 0행을 갱신하고, 신규/테스트 DB에서
    '기본 대화 = 내 모든 기존 기록' 불변식이 유지된다.
    """
    thread = db.query(Thread).filter(Thread.user_id == user_id).order_by(Thread.id.asc()).first()
    if thread is not None:
        return thread
    thread = Thread(user_id=user_id, title=DEFAULT_THREAD_TITLE)
    db.add(thread)
    db.flush()  # thread.id 확보
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
    """메시지 저장 성공 후: 최초 메시지로 제목 자동 생성 + 활동 시각 갱신.

    실패해도 치명적이지 않아 except에서 조용히 rollback(메시지 저장은 이미 커밋됨).
    """
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
