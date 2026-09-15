"""관리자 전용 기능 — 전체 대화 조회·해시 현황·사용자 삭제. 권한은 서버 CLI로만 부여한다."""

import json
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import E
from app.database import Base, get_db
from app.deps import get_admin_user
from app.enums import ChatStatus
from app.logging_config import REQUEST_ID, log_event
from app.models import AuditEvent, RequestLog, User
from app.policies import DEFAULT_PAGE_SIZE, MAX_AUDIT_REASON_CHARS, MAX_LOG_PAGE_SIZE
from app.repositories.chat_logs import list_logs
from app.schemas import (
    AdminChatLogOut,
    AdminDbRows,
    AdminDbTableOut,
    AdminEventOut,
    AdminEventPage,
    AdminLogPage,
    AdminRequestLogOut,
    AdminRequestLogPage,
    DeletedUserOut,
    LogStatus,
    PasswordHashStatusOut,
)
from app.services.admin import is_admin
from app.services.filter_query import parse_filter
from app.services.security import is_peppered_hash
from app.services.sessions import revoke_user_sessions
from app.services.suggest import MAX_SUGGESTIONS, SUGGESTORS

logger = logging.getLogger("app.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get(
    "/chats",
    response_model=AdminLogPage,
    summary="관리자 대화 로그 조회",
    description=(
        "명시적 앱 관리자만 전체 사용자 기록 조회 가능. 원문은 관리자 화면에만 "
        "표시하고 접근 이벤트에는 원문을 기록하지 않습니다."
    ),
    responses={401: {"description": "로그인 필요"}, 403: {"description": "앱 관리자 권한 필요"}},
)
def all_chats(
    filter_query: str = Query(default="", max_length=200, alias="filter"),
    limit: int = DEFAULT_PAGE_SIZE,
    user_id: int | None = Query(default=None, gt=0),
    thread_id: int | None = Query(default=None, gt=0),
    status_: LogStatus | None = Query(default=None, alias="status"),
    before_id: int | None = Query(default=None, gt=0),
    reason: str = Query(
        default="",
        max_length=MAX_AUDIT_REASON_CHARS,
        description="열람 사유 — 감사 로그에 기록",
    ),
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    fq = parse_filter(filter_query, {"user_id", "thread_id", "status", "q"})
    effective_limit = max(1, min(limit, MAX_LOG_PAGE_SIZE))
    chat_status = fq.get("status", status_)
    if chat_status not in (None, "success", "ai_error"):
        chat_status = None
    rows = list_logs(
        db,
        user_id=fq.int_or("user_id", user_id),
        thread_id=fq.int_or("thread_id", thread_id),
        search=fq.search,
        limit=effective_limit,
        status=chat_status,
        before_id=before_id,
    )
    audit = {
        "user_id": user.id,
        "filter_user_id": user_id,
        "filter_thread_id": thread_id,
        "result_count": len(rows),
        "before_id": before_id,
    }
    if reason.strip():
        audit["reason"] = reason.strip()[:MAX_AUDIT_REASON_CHARS]
    log_event(logger, E.ADMIN_LOGS_VIEWED, **audit)
    return AdminLogPage(
        items=[AdminChatLogOut.model_validate(row) for row in rows],
        next_before_id=rows[-1].id if len(rows) == effective_limit else None,
    )


@router.get(
    "/security/password-hashes",
    response_model=PasswordHashStatusOut,
    summary="비밀번호 해시 마이그레이션 현황",
    description=(
        "페퍼(p2:) 적용 해시와 레거시(페퍼 이전) 해시의 사용자 수를 보고한다. "
        "legacy가 0이 되면 verify_password_legacy 폴백을 제거해도 안전하다"
        "(docs/OPERATIONS.md '레거시 폴백 제거 기준' 참조)."
    ),
    responses={401: {"description": "로그인 필요"}, 403: {"description": "앱 관리자 권한 필요"}},
)
def password_hash_status(
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    rows = db.query(User).all()
    peppered = sum(1 for u in rows if is_peppered_hash(u.password_hash))
    log_event(
        logger,
        E.ADMIN_HASH_STATUS_VIEWED,
        user_id=user.id,
        total=len(rows),
        legacy=len(rows) - peppered,
    )
    return PasswordHashStatusOut(
        total=len(rows),
        peppered=peppered,
        legacy=len(rows) - peppered,
    )


@router.delete(
    "/users/{user_id}",
    response_model=DeletedUserOut,
    summary="사용자 삭제(테스트 계정 정리 등)",
    description=(
        "관리자 전용. 대화 기록·세션 폐기 표시·재설정 토큰이 함께 삭제되고(FK CASCADE) "
        "해당 사용자의 서버 측 세션도 즉시 폐기한다. 자기 자신과 다른 관리자는 삭제할 수 없다."
    ),
    responses={
        400: {"description": "자기 자신 또는 다른 관리자 삭제 시도"},
        401: {"description": "로그인 필요"},
        403: {"description": "앱 관리자 권한 필요"},
        404: {"description": "존재하지 않는 사용자"},
    },
)
def delete_user(
    user_id: int,
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 사용자예요.")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="자기 자신은 삭제할 수 없어요.")
    if is_admin(db, target):
        raise HTTPException(status_code=400, detail="다른 관리자 계정은 삭제할 수 없어요.")
    revoke_user_sessions(db, target, backoff_seconds=1)
    deleted_email, deleted_id = target.email, target.id
    db.delete(target)
    db.commit()
    log_event(
        logger,
        E.ADMIN_USER_DELETED,
        user_id=user.id,
        deleted_user_id=deleted_id,
        email_domain=deleted_email.split("@")[-1],
        level=logging.WARNING,
    )
    return DeletedUserOut(user_id=deleted_id, email=deleted_email)


def _utcnow():
    from app.models import utcnow

    return utcnow()


@router.get(
    "/stats",
    summary="관리자 대시보드 통계",
    description="사용자·스레드·대화·성공률·최근 24시간 요청/이벤트 수. 관리자 권한 필요.",
)
def stats(user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """사용자·스레드·대화·성공률·최근 24시간 요청 수를 집계한다."""
    from app.models import ChatLog, Thread

    horizon = _utcnow() - timedelta(hours=24)
    stats = {
        "users": db.query(User).count(),
        "threads": db.query(Thread).count(),
        "chats": db.query(ChatLog).count(),
        "chats_success": db.query(ChatLog).filter(ChatLog.status == ChatStatus.SUCCESS).count(),
        "chats_ai_error": db.query(ChatLog).filter(ChatLog.status == ChatStatus.AI_ERROR).count(),
        "events_24h": db.query(AuditEvent).filter(AuditEvent.created_at >= horizon).count(),
        "requests_24h": db.query(RequestLog).filter(RequestLog.created_at >= horizon).count(),
        "requests_total": db.query(RequestLog).count(),
    }
    log_event(logger, E.ADMIN_STATS_VIEWED, user_id=user.id, request_id=REQUEST_ID.get() or "")
    return stats


def _page(items, limit: int):
    """id 내림차순 페이지 — 다음 커서는 마지막 행 id."""
    next_before = items[-1].id if len(items) == limit else None
    return items, next_before


@router.get(
    "/events",
    response_model=AdminEventPage,
    summary="이벤트 로그 조회",
    description=(
        "감사 이벤트 DB 영속분을 최신순으로 반환한다. event로 이름 필터, "
        "before_id로 이전 페이지. 마스킹된 메타데이터만 담긴다(원문 질문·응답 제외)."
    ),
)
def all_events(
    filter_query: str = Query(default="", max_length=200, alias="filter"),
    event: str | None = Query(default=None, max_length=64),
    user_id: int | None = Query(default=None, gt=0),
    before_id: int | None = Query(default=None, gt=0),
    limit: int = DEFAULT_PAGE_SIZE,
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    search: str | None = None,
):
    fq = parse_filter(filter_query, {"event", "user", "q"})
    effective = max(1, min(limit, MAX_LOG_PAGE_SIZE))
    query = db.query(AuditEvent)
    if fq.get("event", event):
        query = query.filter(AuditEvent.event == fq.get("event", event))
    effective_user = fq.int_or("user", user_id)
    if effective_user:
        query = query.filter(AuditEvent.user_id == effective_user)
    effective_search = fq.search or search
    if effective_search:
        query = query.filter(AuditEvent.fields_json.ilike(f"%{effective_search}%"))
    if before_id:
        query = query.filter(AuditEvent.id < before_id)
    rows = query.order_by(AuditEvent.id.desc()).limit(effective).all()
    items = [
        AdminEventOut(
            id=row.id,
            created_at=row.created_at,
            event=row.event,
            user_id=row.user_id,
            request_id=row.request_id,
            fields=json.loads(row.fields_json or "{}"),
        )
        for row in rows
    ]
    _, next_before = _page(rows, effective)
    log_event(
        logger,
        E.ADMIN_EVENTS_VIEWED,
        user_id=user.id,
        filter_event=event,
        result_count=len(rows),
        request_id=REQUEST_ID.get() or "",
    )
    return AdminEventPage(items=items, next_before_id=next_before)


@router.get(
    "/network",
    response_model=AdminRequestLogPage,
    summary="네트워크 로그 조회",
    description=(
        "/api/ 요청 기록(method·path·status·지연)을 최신순으로 반환한다. "
        "status로 상태코드 필터, before_id로 이전 페이지. 보존 한도는 5,000건."
    ),
)
def all_requests(
    filter_query: str = Query(default="", max_length=200, alias="filter"),
    status_: int | None = Query(default=None, alias="status"),
    before_id: int | None = Query(default=None, gt=0),
    limit: int = DEFAULT_PAGE_SIZE,
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    path: str | None = None,
    method: str | None = None,
    user_id: int | None = None,
):
    fq = parse_filter(filter_query, {"path", "method", "status", "user"})
    effective = max(1, min(limit, MAX_LOG_PAGE_SIZE))
    query = db.query(RequestLog)
    effective_status = fq.int_or("status", status_)
    if effective_status:
        query = query.filter(RequestLog.status == effective_status)
    effective_path = fq.get("path", path)
    if effective_path:
        query = query.filter(RequestLog.path.ilike(f"%{effective_path}%"))
    effective_method = (fq.get("method", method) or "").upper() or None
    if effective_method:
        query = query.filter(RequestLog.method == effective_method)
    effective_user = fq.int_or("user", user_id)
    if effective_user:
        query = query.filter(RequestLog.user_id == effective_user)
    if before_id:
        query = query.filter(RequestLog.id < before_id)
    rows = query.order_by(RequestLog.id.desc()).limit(effective).all()
    items = [
        AdminRequestLogOut(
            id=row.id,
            created_at=row.created_at,
            method=row.method,
            path=row.path,
            status=row.status,
            user_id=row.user_id,
            latency_ms=row.latency_ms,
            request_id=row.request_id,
        )
        for row in rows
    ]
    _, next_before = _page(rows, effective)
    log_event(
        logger,
        E.ADMIN_NETWORK_VIEWED,
        user_id=user.id,
        filter_status=status_,
        result_count=len(rows),
        request_id=REQUEST_ID.get() or "",
    )
    return AdminRequestLogPage(items=items, next_before_id=next_before)


@router.get(
    "/db/tables",
    response_model=list[AdminDbTableOut],
    summary="DB 테이블 목록·행수",
    description="앱이 소유한 테이블만 화이트리스트로 노출한다 — 임의 SQL은 없다.",
)
def db_tables(user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """앱이 소유한 테이블만 화이트리스트로 노출한다 — 임의 SQL은 없다."""
    from sqlalchemy import text

    names = sorted(Base.metadata.tables)
    out = []
    for name in names:
        count = db.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
        out.append(AdminDbTableOut(name=name, rows=int(count)))
    log_event(
        logger,
        E.ADMIN_DB_VIEWED,
        user_id=user.id,
        scope="tables",
        request_id=REQUEST_ID.get() or "",
    )
    return out


@router.get(
    "/db/tables/{name}/rows",
    response_model=AdminDbRows,
    summary="DB 테이블 행 미리보기",
    description=(
        "화이트리스트 테이블의 최근 행을 id 내림차순으로 반환한다. "
        "읽기 전용이며 존재하지 않는 이름은 404."
    ),
)
def db_table_rows(
    name: str,
    before_id: int | None = Query(default=None, gt=0),
    limit: int = DEFAULT_PAGE_SIZE,
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """화이트리스트 테이블의 최근 행을 id 내림차순으로 반환 — 읽기 전용·임의 SQL 없음."""
    from sqlalchemy import text

    table = Base.metadata.tables.get(name)
    if table is None or "id" not in table.columns:
        raise HTTPException(status_code=404, detail="존재하지 않는 테이블이에요.")
    effective = max(1, min(limit, MAX_LOG_PAGE_SIZE))
    sql = f'SELECT * FROM "{name}"'  # noqa: S608 — 테이블명은 화이트리스트 검증됨
    params: dict = {}
    if before_id:
        sql += " WHERE id < :before_id"
        params["before_id"] = before_id
    sql += " ORDER BY id DESC LIMIT :lim"
    params["lim"] = effective
    rows_raw = db.execute(text(sql), params).mappings().all()
    columns = [c.name for c in table.columns]
    rows = [
        {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(r).items()}
        for r in rows_raw
    ]
    log_event(
        logger,
        E.ADMIN_DB_VIEWED,
        user_id=user.id,
        scope=name,
        result_count=len(rows),
        request_id=REQUEST_ID.get() or "",
    )
    return AdminDbRows(
        table=name,
        columns=columns,
        rows=rows,
        next_before_id=rows_raw[-1]["id"] if len(rows_raw) == effective else None,
    )


@router.get("/suggest", summary="필터 값 자동완성 후보")
def suggest_values(
    field: str = Query(max_length=16, description="후보 종류 — 화이트리스트"),
    q: str = Query(default="", max_length=64, description="입력 중인 값"),
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """관리자 콘솔 필터박스의 값 후보. 화이트리스트 밖 필드는 400."""
    suggestor = SUGGESTORS.get(field)
    if suggestor is None:
        raise HTTPException(status_code=400, detail="지원하지 않는 필드예요.")
    clean = q.strip()[:64]
    items = suggestor(db, clean)
    return {"field": field, "items": items[:MAX_SUGGESTIONS]}
