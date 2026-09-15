"""관리자 콘솔·감사·통계·DB 검사 관련 DB 쿼리 집중 계층."""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import Base
from app.enums import ChatStatus
from app.models import AuditEvent, ChatLog, RequestLog, Thread, User
from app.policies import DEFAULT_PAGE_SIZE, MAX_LOG_PAGE_SIZE
from app.services.security import is_peppered_hash


def _escape_like(value: str) -> str:
    """LIKE 와일드카드를 문자 그대로 취급하게 이스케이프한다(인젝션 방어)."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_admin_dashboard_counts(db: Session, horizon: datetime) -> dict:
    """사용자·스레드·대화·성공률·최근 24시간 요청 수를 집계한다."""
    return {
        "users": db.query(User).count(),
        "threads": db.query(Thread).count(),
        "chats": db.query(ChatLog).count(),
        "chats_success": db.query(ChatLog).filter(ChatLog.status == ChatStatus.SUCCESS).count(),
        "chats_ai_error": db.query(ChatLog).filter(ChatLog.status == ChatStatus.AI_ERROR).count(),
        "events_24h": db.query(AuditEvent).filter(AuditEvent.created_at >= horizon).count(),
        "requests_24h": db.query(RequestLog).filter(RequestLog.created_at >= horizon).count(),
        "requests_total": db.query(RequestLog).count(),
    }


def list_audit_events(
    db: Session,
    *,
    event: str | None = None,
    user_id: int | None = None,
    search: str | None = None,
    before_id: int | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> list[AuditEvent]:
    """감사 이벤트 DB 영속분을 최신순으로 조회한다."""
    effective_limit = max(1, min(limit, MAX_LOG_PAGE_SIZE))
    query = db.query(AuditEvent)
    if event:
        query = query.filter(AuditEvent.event == event)
    if user_id:
        query = query.filter(AuditEvent.user_id == user_id)
    if search:
        query = query.filter(AuditEvent.fields_json.ilike(f"%{_escape_like(search)}%", escape="\\"))
    if before_id:
        query = query.filter(AuditEvent.id < before_id)
    return query.order_by(AuditEvent.id.desc()).limit(effective_limit).all()


def list_request_logs(
    db: Session,
    *,
    path: str | None = None,
    method: str | None = None,
    status_: int | None = None,
    user_id: int | None = None,
    before_id: int | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> list[RequestLog]:
    """/api/ 요청 기록(네트워크 로그)을 최신순으로 조회한다."""
    effective_limit = max(1, min(limit, MAX_LOG_PAGE_SIZE))
    query = db.query(RequestLog)
    if status_:
        query = query.filter(RequestLog.status == status_)
    if path:
        query = query.filter(RequestLog.path.ilike(f"%{_escape_like(path)}%", escape="\\"))
    if method:
        query = query.filter(RequestLog.method == method.upper())
    if user_id:
        query = query.filter(RequestLog.user_id == user_id)
    if before_id:
        query = query.filter(RequestLog.id < before_id)
    return query.order_by(RequestLog.id.desc()).limit(effective_limit).all()


def get_table_counts(db: Session) -> list[tuple[str, int]]:
    """앱이 소유한 테이블 목록과 각 테이블의 행 수를 조회한다."""
    names = sorted(Base.metadata.tables)
    out: list[tuple[str, int]] = []
    for name in names:
        count = db.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
        out.append((name, int(count)))
    return out


def get_table_rows(
    db: Session,
    table_name: str,
    *,
    before_id: int | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> tuple[list[dict], list[str]] | None:
    """화이트리스트 테이블의 최근 행과 열 목록을 id 내림차순으로 조회한다."""
    table = Base.metadata.tables.get(table_name)
    if table is None or "id" not in table.columns:
        return None
    effective_limit = max(1, min(limit, MAX_LOG_PAGE_SIZE))
    sql = f'SELECT * FROM "{table_name}"'
    params: dict = {"lim": effective_limit}
    if before_id:
        sql += " WHERE id < :before_id"
        params["before_id"] = before_id
    sql += " ORDER BY id DESC LIMIT :lim"
    rows_raw = db.execute(text(sql), params).mappings().all()
    columns = [c.name for c in table.columns]
    rows = [
        {
            c: (row[c].isoformat() if hasattr(row.get(c), "isoformat") else row.get(c))
            for c in columns
        }
        for row in rows_raw
    ]
    return rows, columns


def count_password_hashes(db: Session) -> tuple[int, int, int]:
    """비밀번호 해시 현황(전체, 페퍼 적용, 레거시)을 집계한다."""
    rows = db.query(User.password_hash).all()
    total = len(rows)
    peppered = sum(1 for (h,) in rows if is_peppered_hash(h))
    legacy = total - peppered
    return total, peppered, legacy


def find_user_by_email_substring(db: Session, email_pattern: str) -> User | None:
    """이메일 부분일치로 사용자를 검색한다."""
    escaped = _escape_like(email_pattern)
    return (
        db.query(User)
        .filter(User.email.ilike(f"%{escaped}%", escape="\\"))
        .order_by(User.id)
        .first()
    )


def get_users_metadata_by_ids(db: Session, user_ids: set[int]) -> dict[int, dict]:
    """사용자 ID 집합으로 이메일과 닉네임 메타데이터를 일괄 조회한다."""
    if not user_ids:
        return {}
    users_q = db.query(User.id, User.email, User.nickname).filter(User.id.in_(user_ids))
    return {uid: {"email": email, "nickname": nick} for uid, email, nick in users_q}


def get_threads_for_admin_logs(
    db: Session, target_user_id: int | None, log_thread_ids: set[int]
) -> list[dict]:
    """관리자 로그 화면의 스레드 필터 드롭다운 옵션 목록을 생성한다."""
    if target_user_id is not None:
        thread_rows = (
            db.query(Thread.id, Thread.title)
            .filter(Thread.user_id == target_user_id)
            .limit(50)
            .all()
        )
    else:
        thread_rows = (
            db.query(Thread.id, Thread.title).filter(Thread.id.in_(log_thread_ids)).all()
            if log_thread_ids
            else []
        )
    return [
        {"id": tid, "label": f"#{tid} · {title or '기본 대화'}"}
        for tid, title in sorted(thread_rows)
    ]
