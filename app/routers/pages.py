"""HTML 페이지. 비로그인 보호 화면은 /login으로 이동하고 API는 401을 사용한다."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.audit import E
from app.config import settings
from app.database import get_db
from app.deps import resolve_session_user
from app.logging_config import log_event
from app.models import Thread, User
from app.repositories.chat_logs import list_logs
from app.repositories.users import find_by_email
from app.routers.admin import all_events, all_requests, db_table_rows, db_tables, stats
from app.services.admin import is_admin
from app.services.filter_query import parse_filter
from app.services.password_reset import is_reset_token_valid

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["asset_v"] = settings.build_sha[:7] or "dev"
router = APIRouter(include_in_schema=False)
logger = logging.getLogger("app.admin")


def _kst(value):
    """UTC 저장 시각을 KST(UTC+9) 표시 문자열로 변환 — 서버 TZ 설정과 무관하게 고정 오프셋."""
    from datetime import timedelta

    return (value + timedelta(hours=9)).strftime("%m-%d %H:%M")


templates.env.filters["kst"] = _kst


def _session_user(request: Request, db: Session) -> User | None:
    user = resolve_session_user(request, db)
    if user is not None:
        request.state.authenticated_user_id = user.id
    return user


def _context(db: Session, user: User) -> dict:
    return {"nickname": user.nickname, "is_admin": is_admin(db, user)}


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            **_context(db, user),
            "demo_mode": not settings.ai_api_key,
            "context_turns": settings.context_turns,
            "max_question_length": settings.max_question_length,
        },
    )


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    if _session_user(request, db):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"mode": "login"})


@router.get("/signup")
def signup_page(request: Request, db: Session = Depends(get_db)):
    if _session_user(request, db):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"mode": "signup"})


@router.get("/forgot-password")
def forgot_password_page(request: Request, db: Session = Depends(get_db)):
    """비밀번호 찾기 화면 — 로그인 없이 접근 가능. 메일 설정 상태만 안내한다."""
    if _session_user(request, db):
        return RedirectResponse("/", status_code=302)
    smtp_ready = bool(settings.smtp_host) or settings.debug
    return templates.TemplateResponse(
        request, "forgot-password.html", {"mode": "forgot", "smtp_ready": smtp_ready}
    )


@router.get("/reset-password")
def reset_password_page(
    request: Request, token: str = Query(default=""), db: Session = Depends(get_db)
):
    """재설정 화면 — 토큰은 소모하지 않고 표시용으로만 검증한다(실제 사용은 POST에서)."""
    if _session_user(request, db):
        return RedirectResponse("/", status_code=302)
    token_valid = is_reset_token_valid(db, token)
    return templates.TemplateResponse(
        request,
        "reset-password.html",
        {"mode": "reset", "token": token, "token_valid": token_valid},
    )


@router.get("/logs")
def logs_page(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    rows = list_logs(db, user_id=user.id, limit=100)
    return templates.TemplateResponse(request, "logs.html", {**_context(db, user), "logs": rows})


LOG_FILTER_KEYS = {"email", "thread", "status", "q"}


@router.get("/admin/logs")
def admin_logs_page(
    request: Request,
    filter_query: str = Query(default="", max_length=200, alias="filter"),
    email: str = Query(default="", max_length=255, description="사용자 이메일 — 정확히 일치"),
    thread: int | None = Query(
        default=None, gt=0, description="스레드 ID — 같은 대화끼리 묶어 본다"
    ),
    before_id: int | None = Query(default=None, gt=0),
    reason: str = Query(default="", max_length=200, description="열람 사유 — 감사 로그에 기록"),
    db: Session = Depends(get_db),
):
    user = _session_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not is_admin(db, user):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요한 기능이에요.")
    fq = parse_filter(filter_query, LOG_FILTER_KEYS)
    clean_email = (fq.get("email") or email).strip().lower()
    thread = fq.int_or("thread", thread)
    log_status = fq.get("status")
    if log_status not in (None, "success", "ai_error"):
        log_status = None
    target = find_by_email(db, clean_email) if clean_email else None
    user_not_found = bool(clean_email) and target is None
    thread_exists = (
        thread is None or db.query(Thread.id).filter(Thread.id == thread).first() is not None
    )
    if user_not_found or not thread_exists:
        rows = []
    else:
        rows = list_logs(
            db,
            user_id=(target.id if target else None),
            thread_id=thread,
            status=log_status,
            search=fq.search,
            before_id=before_id,
            limit=50,
        )
    audit = {
        "user_id": user.id,
        "filter_email": clean_email or None,
        "result_count": len(rows),
        "before_id": before_id,
    }
    cleaned_reason = reason.strip()[:200]
    if cleaned_reason:
        audit["reason"] = cleaned_reason
    log_event(logger, E.ADMIN_LOGS_VIEWED, **audit)
    user_infos = {}
    if rows:
        ids = {row.user_id for row in rows}
        users_q = db.query(User.id, User.email, User.nickname).filter(User.id.in_(ids))
        for uid, u_email, nick in users_q:
            user_infos[uid] = {"email": u_email, "nickname": nick}
    # 스레드 콤보 옵션: 이메일 필터면 그 사용자의 스레드, 아니면 화면의 스레드들
    if target is not None:
        thread_rows = (
            db.query(Thread.id, Thread.title).filter(Thread.user_id == target.id).limit(50).all()
        )
    else:
        log_thread_ids = {row.thread_id for row in rows if row.thread_id is not None}
        thread_rows = (
            db.query(Thread.id, Thread.title).filter(Thread.id.in_(log_thread_ids)).all()
            if log_thread_ids
            else []
        )
    thread_options = [
        {
            "id": tid,
            "label": f"#{tid} · {title or '기본 대화'}",
        }
        for tid, title in sorted(thread_rows)
    ]
    return templates.TemplateResponse(
        request,
        "admin-logs.html",
        {
            **_context(db, user),
            "logs": rows,
            "filter_email": clean_email,
            "user_not_found": user_not_found,
            "user_infos": user_infos,
            "filter_reason": cleaned_reason,
            "filter_thread": thread,
            "filter_query": filter_query,
            "filter_errors": fq.errors,
            "filter_keys": "email,thread,status,q",
            "thread_options": thread_options,
            "next_before_id": rows[-1].id if len(rows) == 50 else None,
            "admin_section": "logs",
        },
    )


def _admin_gate(request: Request, db: Session):
    """관리자 페이지 공통 게이트 — 비로그인은 로그인으로, 관리자 아님은 403."""
    user = _session_user(request, db)
    if user is None:
        return None, RedirectResponse("/login", status_code=302)
    if not is_admin(db, user):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요한 기능이에요.")
    return user, None


@router.get("/admin")
def admin_dashboard_page(request: Request, db: Session = Depends(get_db)):
    """관리자 콘솔 허브 — 통계 카드와 서브메뉴(#189)."""
    user, redirect = _admin_gate(request, db)
    if redirect:
        return redirect
    data = stats(user=user, db=db)
    return templates.TemplateResponse(
        request,
        "admin-dashboard.html",
        {**_context(db, user), **data, "admin_section": "dashboard"},
    )


EVENT_FILTER_KEYS = {"event", "user", "q"}


@router.get("/admin/events")
def admin_events_page(
    request: Request,
    filter_query: str = Query(default="", max_length=200, alias="filter"),
    event: str = Query(default="", max_length=64),
    before_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    user, redirect = _admin_gate(request, db)
    if redirect:
        return redirect
    fq = parse_filter(filter_query, EVENT_FILTER_KEYS)
    page = all_events(
        user=user,
        db=db,
        event=fq.get("event", event.strip()) or None,
        user_id=fq.int_or("user"),
        search=fq.search,
        before_id=before_id,
        limit=50,
    )
    return templates.TemplateResponse(
        request,
        "admin-events.html",
        {
            **_context(db, user),
            "events": page.items,
            "filter_query": filter_query,
            "filter_errors": fq.errors,
            "filter_keys": "event,user,q",
            "next_before_id": page.next_before_id,
            "admin_section": "events",
        },
    )


NETWORK_FILTER_KEYS = {"path", "method", "status", "user"}


@router.get("/admin/network")
def admin_network_page(
    request: Request,
    filter_query: str = Query(default="", max_length=200, alias="filter"),
    status: int | None = Query(default=None, gt=0),
    before_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    user, redirect = _admin_gate(request, db)
    if redirect:
        return redirect
    fq = parse_filter(filter_query, NETWORK_FILTER_KEYS)
    page = all_requests(
        user=user,
        db=db,
        status_=fq.int_or("status", status),
        path=fq.get("path"),
        method=fq.get("method"),
        user_id=fq.int_or("user"),
        before_id=before_id,
        limit=50,
    )
    return templates.TemplateResponse(
        request,
        "admin-network.html",
        {
            **_context(db, user),
            "requests": page.items,
            "filter_query": filter_query,
            "filter_errors": fq.errors,
            "filter_keys": "path,method,status,user",
            "next_before_id": page.next_before_id,
            "admin_section": "network",
        },
    )


DB_FILTER_KEYS = {"table"}


@router.get("/admin/db")
def admin_db_page(
    request: Request,
    filter_query: str = Query(default="", max_length=200, alias="filter"),
    table: str = Query(default="", max_length=64),
    before_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    user, redirect = _admin_gate(request, db)
    if redirect:
        return redirect
    fq = parse_filter(filter_query, DB_FILTER_KEYS)
    tables = db_tables(user=user, db=db)
    clean_name = (fq.get("table") or table).strip()
    rows_page = None
    not_found = False
    if clean_name:
        try:
            rows_page = db_table_rows(
                user=user, db=db, name=clean_name, before_id=before_id, limit=50
            )
        except HTTPException:
            not_found = True
    return templates.TemplateResponse(
        request,
        "admin-db.html",
        {
            **_context(db, user),
            "tables": tables,
            "current_table": clean_name,
            "filter_query": filter_query,
            "filter_errors": fq.errors,
            "filter_keys": "table",
            "rows_page": rows_page,
            "table_not_found": not_found,
            "next_before_id": rows_page.next_before_id if rows_page else None,
            "admin_section": "db",
        },
    )
