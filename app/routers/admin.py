"""관리자 전용 전체 대화 조회. 기본 권한 없음; 서버 CLI로만 권한을 부여한다."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_admin_user
from app.logging_config import log_event
from app.models import User
from app.policies import MAX_LOG_PAGE_SIZE
from app.repositories.chat_logs import list_logs
from app.schemas import AdminChatLogOut, AdminLogPage, LogStatus

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
    limit: int = 50,
    user_id: int | None = Query(default=None, gt=0),
    status_: LogStatus | None = Query(default=None, alias="status"),
    before_id: int | None = Query(default=None, gt=0),
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    effective_limit = max(1, min(limit, MAX_LOG_PAGE_SIZE))
    rows = list_logs(
        db, user_id=user_id, limit=effective_limit, status=status_, before_id=before_id
    )
    log_event(
        logger,
        "admin_logs_viewed",
        user_id=user.id,
        filter_user_id=user_id,
        result_count=len(rows),
        before_id=before_id,
    )
    return AdminLogPage(
        items=[AdminChatLogOut.model_validate(row) for row in rows],
        next_before_id=rows[-1].id if len(rows) == effective_limit else None,
    )
