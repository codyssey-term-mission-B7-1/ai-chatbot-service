"""사용자별 대화 조회 API. 성공 필터를 limit보다 먼저 적용한다."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.repositories import threads as threads_repo
from app.repositories.chat_logs import list_logs
from app.schemas import ChatLogOut, LogStatus

router = APIRouter(prefix="/api/me", tags=["logs"])


@router.get(
    "/chats",
    response_model=list[ChatLogOut],
    summary="내 대화 로그 조회",
    description=(
        "본인 기록만 최신순으로 반환. limit은 1~200으로 제한. "
        "status=success로 필터한 뒤 limit을 적용하면 AI 문맥과 일치합니다. "
        "before_id로 이전 페이지 조회. thread_id로 특정 대화만 조회. created_at은 UTC Z 형식."
    ),
    responses={
        401: {"description": "로그인 필요"},
        404: {"description": "thread_id가 존재하지 않거나 내 대화가 아님"},
    },
)
def my_chats(
    limit: int = 50,
    status_: LogStatus | None = Query(default=None, alias="status"),
    before_id: int | None = Query(default=None, gt=0),
    thread_id: int | None = Query(default=None, ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if thread_id is not None and threads_repo.get_thread(db, thread_id, user_id=user.id) is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없어요.")
    return list_logs(
        db, user_id=user.id, limit=limit, status=status_, before_id=before_id, thread_id=thread_id
    )
