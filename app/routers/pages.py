"""HTML 페이지 — 채팅/로그인/회원가입/내 기록."""
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import ChatLog, User

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)


def _session_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    return db.get(User, int(user_id)) if user_id else None


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "chat.html", {
        "nickname": user.nickname,
        "demo_mode": settings.ai_api_key is None,
        "context_turns": settings.context_turns,
    })


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
def logs_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(ChatLog).filter(ChatLog.user_id == user.id)
        .order_by(ChatLog.id.desc()).limit(100).all()
    )
    return templates.TemplateResponse(
        request, "logs.html", {"nickname": user.nickname, "logs": logs}
    )
