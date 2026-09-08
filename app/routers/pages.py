"""HTML 페이지. 비로그인 보호 화면은 /login으로 이동하고 API는 401을 사용한다."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import resolve_session_user
from app.logging_config import log_event
from app.models import User
from app.repositories.chat_logs import list_logs
from app.services.admin import is_admin

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter(include_in_schema=False)
logger = logging.getLogger("app.admin")


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


@router.get("/logs")
def logs_page(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    rows = list_logs(db, user_id=user.id, limit=100)
    return templates.TemplateResponse(request, "logs.html", {**_context(db, user), "logs": rows})


@router.get("/admin/logs")
def admin_logs_page(
    request: Request,
    user_id: int | None = Query(default=None, gt=0),
    before_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    user = _session_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    if not is_admin(db, user):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요한 기능이에요.")
    rows = list_logs(db, user_id=user_id, before_id=before_id, limit=50)
    log_event(
        logger,
        "admin_logs_viewed",
        user_id=user.id,
        filter_user_id=user_id,
        result_count=len(rows),
        before_id=before_id,
    )
    return templates.TemplateResponse(
        request,
        "admin-logs.html",
        {
            **_context(db, user),
            "logs": rows,
            "filter_user_id": user_id,
            "next_before_id": rows[-1].id if len(rows) == 50 else None,
        },
    )
