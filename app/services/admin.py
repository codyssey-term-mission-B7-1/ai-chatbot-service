"""앱 관리자 권한 및 관리자 콘솔 서비스 계층.

권한 관리·통계 집계·감사/네트워크 로그·DB 브라우저 비즈니스 로직을 집중 처리한다.
"""

import json
import logging
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import E
from app.logging_config import REQUEST_ID, log_event
from app.models import AdminGrant, User, utcnow
from app.policies import DEFAULT_PAGE_SIZE, MAX_AUDIT_REASON_CHARS, MAX_LOG_PAGE_SIZE
from app.repositories import admin as admin_repo
from app.repositories.chat_logs import list_logs
from app.repositories.users import find_by_email
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
from app.services.filter_query import parse_filter
from app.services.sessions import revoke_user_sessions

logger = logging.getLogger("app.admin")
DEMO_EMAILS = frozenset({"demo@demo.com", "tester@demo.com", "admin@demo.com"})


def is_admin(db: Session, user: User) -> bool:
    """사용자의 명시적 관리자 권한 부여 여부를 확인한다."""
    grant = db.get(AdminGrant, user.id)
    return grant is not None and grant.granted_email == user.email


def grant_admin(db: Session, email: str) -> User:
    """신뢰된 서버 CLI에서만 호출. 가입 API로는 권한을 받을 수 없다."""
    email = email.strip().lower()
    if email in DEMO_EMAILS:
        raise ValueError("공개 비밀번호를 사용하는 데모 계정에는 관리자 권한을 부여할 수 없습니다.")
    user = find_by_email(db, email)
    if user is None:
        raise ValueError("먼저 전용 관리자 계정을 회원가입으로 생성하세요.")
    grant = db.get(AdminGrant, user.id)
    if grant is None:
        db.add(AdminGrant(user_id=user.id, granted_email=user.email))
    else:
        grant.granted_email = user.email
    db.commit()
    return user


def revoke_admin(db: Session, email: str) -> bool:
    """관리자 권한을 회수한다."""
    user = find_by_email(db, email.strip().lower())
    if user is None:
        return False
    grant = db.get(AdminGrant, user.id)
    if grant is None:
        return False
    db.delete(grant)
    db.commit()
    return True


def get_admin_dashboard_stats(db: Session, user: User) -> dict:
    """사용자·스레드·대화·성공률·최근 24시간 요청 수를 집계한다."""
    horizon = utcnow() - timedelta(hours=24)
    stats_data = admin_repo.get_admin_dashboard_counts(db, horizon)
    log_event(logger, E.ADMIN_STATS_VIEWED, user_id=user.id, request_id=REQUEST_ID.get() or "")
    return stats_data


def get_admin_events_page(
    db: Session,
    user: User,
    *,
    filter_query: str = "",
    event: str | None = None,
    user_id: int | None = None,
    before_id: int | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    search: str | None = None,
) -> AdminEventPage:
    """감사 이벤트 DB 영속분을 최신순으로 조회하여 DTO로 반환한다."""
    fq = parse_filter(filter_query, {"event", "user", "q"})
    effective = max(1, min(limit, MAX_LOG_PAGE_SIZE))
    effective_event = fq.get("event", event)
    effective_user = fq.int_or("user", user_id)
    effective_search = fq.search or search

    rows = admin_repo.list_audit_events(
        db,
        event=effective_event,
        user_id=effective_user,
        search=effective_search,
        before_id=before_id,
        limit=effective,
    )
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
    next_before = rows[-1].id if len(rows) == effective else None
    log_event(
        logger,
        E.ADMIN_EVENTS_VIEWED,
        user_id=user.id,
        filter_event=event,
        result_count=len(rows),
        request_id=REQUEST_ID.get() or "",
    )
    return AdminEventPage(items=items, next_before_id=next_before)


def get_admin_requests_page(
    db: Session,
    user: User,
    *,
    filter_query: str = "",
    status_: int | None = None,
    before_id: int | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    path: str | None = None,
    method: str | None = None,
    user_id: int | None = None,
) -> AdminRequestLogPage:
    """/api/ 요청 기록(method·path·status·지연)을 최신순으로 조회한다."""
    fq = parse_filter(filter_query, {"path", "method", "status", "user"})
    effective = max(1, min(limit, MAX_LOG_PAGE_SIZE))
    effective_status = fq.int_or("status", status_)
    effective_path = fq.get("path", path)
    effective_method = (fq.get("method", method) or "").upper() or None
    effective_user = fq.int_or("user", user_id)

    rows = admin_repo.list_request_logs(
        db,
        path=effective_path,
        method=effective_method,
        status_=effective_status,
        user_id=effective_user,
        before_id=before_id,
        limit=effective,
    )
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
    next_before = rows[-1].id if len(rows) == effective else None
    log_event(
        logger,
        E.ADMIN_NETWORK_VIEWED,
        user_id=user.id,
        filter_status=status_,
        result_count=len(rows),
        request_id=REQUEST_ID.get() or "",
    )
    return AdminRequestLogPage(items=items, next_before_id=next_before)


def get_admin_db_tables(db: Session, user: User) -> list[AdminDbTableOut]:
    """앱이 소유한 테이블 목록 및 행 수를 조회한다."""
    counts = admin_repo.get_table_counts(db)
    log_event(
        logger,
        E.ADMIN_DB_VIEWED,
        user_id=user.id,
        scope="tables",
        request_id=REQUEST_ID.get() or "",
    )
    return [AdminDbTableOut(name=name, rows=rows) for name, rows in counts]


def get_admin_db_table_rows(
    db: Session,
    user: User,
    name: str,
    *,
    before_id: int | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> AdminDbRows:
    """화이트리스트 테이블의 최근 행을 id 내림차순으로 조회한다."""
    result = admin_repo.get_table_rows(db, name, before_id=before_id, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 테이블이에요.")
    rows, columns = result
    effective = max(1, min(limit, MAX_LOG_PAGE_SIZE))
    next_before = rows[-1]["id"] if len(rows) == effective and "id" in rows[-1] else None
    log_event(
        logger,
        E.ADMIN_DB_VIEWED,
        user_id=user.id,
        scope=name,
        before_id=before_id,
        result_count=len(rows),
        request_id=REQUEST_ID.get() or "",
    )
    return AdminDbRows(table=name, columns=columns, rows=rows, next_before_id=next_before)


def get_password_hash_migration_status(db: Session, user: User) -> PasswordHashStatusOut:
    """비밀번호 해시 마이그레이션 현황을 조회한다."""
    total, peppered, legacy = admin_repo.count_password_hashes(db)
    log_event(
        logger,
        E.ADMIN_HASH_STATUS_VIEWED,
        user_id=user.id,
        total=total,
        legacy=legacy,
    )
    return PasswordHashStatusOut(
        total=total,
        peppered=peppered,
        legacy=legacy,
    )


def delete_user_by_admin(db: Session, user: User, user_id: int) -> DeletedUserOut:
    """관리자 권한으로 사용자를 삭제하고 세션을 즉시 폐기한다."""
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


def get_admin_chats_page(
    db: Session,
    user: User,
    *,
    filter_query: str = "",
    limit: int = DEFAULT_PAGE_SIZE,
    user_id: int | None = None,
    thread_id: int | None = None,
    status_: LogStatus | None = None,
    before_id: int | None = None,
    reason: str = "",
) -> AdminLogPage:
    """관리자 대화 로그를 필터 조회하고 감사 이벤트를 기록한다."""
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
