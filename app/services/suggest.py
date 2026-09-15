"""관리자 콘솔 필터 값 자동완성 — 화이트리스트 필드만, 최소 노출 원칙(#204).

반환값은 식별에 필요한 최소 문자열이다. 이메일은 전체를 반환하지 않고
아이디 앞 2자 + 도메인 마스킹은 하지 않는다(관리자 전용 기능이므로 실제 값을 쓴다).
단, 질문·답변 원문 같은 콘텐츠는 절대 후보로 내보내지 않는다.
"""

from sqlalchemy.orm import Session

from app.models import RequestLog, Thread, User

MAX_SUGGESTIONS = 8


def _escape_like(value: str) -> str:
    """LIKE 와일드카드를 문자 그대로 취급하게 이스케이프한다(인젝션 표면 축소)."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def suggest_emails(db: Session, prefix: str) -> list[str]:
    q = (
        db.query(User.email)
        .filter(User.email.ilike(f"{_escape_like(prefix)}%", escape="\\"))
        .order_by(User.email)
        .limit(MAX_SUGGESTIONS)
    )
    return [row[0] for row in q.all()]


def suggest_threads(db: Session, prefix: str) -> list[dict]:
    """숫자면 ID 일치, 아니면 제목 부분일치 — 콘솔 목록 형식 그대로 반환."""
    query = db.query(Thread.id, Thread.title)
    if prefix:
        if prefix.isdigit():
            query = query.filter(Thread.id == int(prefix))
        else:
            query = query.filter(Thread.title.ilike(f"%{_escape_like(prefix)}%", escape="\\"))
    return [
        {"id": row[0], "label": f"#{row[0]} · {row[1] or '기본 대화'}"}
        for row in query.order_by(Thread.id.desc()).limit(MAX_SUGGESTIONS)
    ]


def suggest_event_names(db: Session, prefix: str) -> list[str]:
    from app.audit import ALL_EVENTS

    names = sorted(ALL_EVENTS)
    if prefix:
        names = [n for n in names if n.startswith(prefix.lower())]
    return names[:MAX_SUGGESTIONS]


def suggest_paths(db: Session, prefix: str) -> list[str]:
    q = (
        db.query(RequestLog.path)
        .filter(RequestLog.path.ilike(f"%{_escape_like(prefix)}%", escape="\\"))
        .distinct()
        .order_by(RequestLog.path)
        .limit(MAX_SUGGESTIONS)
    )
    return [row[0] for row in q.all()]


def suggest_tables(db: Session, prefix: str) -> list[str]:
    from app.database import Base

    names = sorted(Base.metadata.tables)
    if prefix:
        names = [n for n in names if n.startswith(prefix.lower())]
    return names[:MAX_SUGGESTIONS]


SUGGESTORS = {
    "email": lambda db, q: suggest_emails(db, q),
    "thread": lambda db, q: suggest_threads(db, q),
    "event": lambda db, q: suggest_event_names(db, q),
    "path": lambda db, q: suggest_paths(db, q),
    "table": lambda db, q: suggest_tables(db, q),
}
