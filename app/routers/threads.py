"""대화 스레드(새 채팅) API — 생성·목록·삭제.

- POST : 새 대화 생성 (빈 기록으로 시작)
- GET  : 내 대화 목록 (최근 활동순)
- DELETE: 대화 삭제 — 그 대화의 기록도 FK CASCADE로 함께 삭제
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.logging_config import log_event
from app.models import User
from app.repositories import threads as threads_repo
from app.schemas import ThreadOut

logger = logging.getLogger("app.threads")
router = APIRouter(prefix="/api/threads", tags=["threads"])


@router.post(
    "",
    response_model=ThreadOut,
    status_code=201,
    summary="새 대화 시작",
    description="빈 기록의 새 대화(스레드)를 만든다. 사용자는 상한(기본 100)까지 만들 수 있다.",
    responses={
        401: {"description": "로그인 필요"},
        409: {"description": "대화 수 상한 도달"},
    },
)
def create_thread(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if threads_repo.count_threads(db, user_id=user.id) >= settings.max_threads_per_user:
        raise HTTPException(
            status_code=409,
            detail=(
                f"대화 공간이 가득 찼어요. ({settings.max_threads_per_user}개) "
                "오래된 대화를 지우고 시도해 주세요."
            ),
        )
    thread = threads_repo.create_thread(db, user_id=user.id)
    log_event(logger, "thread_created", user_id=user.id, thread_id=thread.id)
    return thread


@router.get(
    "",
    response_model=list[ThreadOut],
    summary="내 대화 목록",
    description="최근 활동순(수정 시각 내림차순) 최대 50개. title이 없으면 '기본 대화'.",
    responses={401: {"description": "로그인 필요"}},
)
def list_my_threads(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return threads_repo.list_threads(db, user_id=user.id)


@router.delete(
    "/{thread_id}",
    summary="대화 삭제",
    description="대화와 그 안의 기록을 함께 삭제한다. 남의 대화는 404.",
    responses={
        401: {"description": "로그인 필요"},
        404: {"description": "존재하지 않거나 내 대화가 아님"},
    },
)
def delete_my_thread(
    thread_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thread = threads_repo.get_thread(db, thread_id, user_id=user.id)
    if thread is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없어요.")
    threads_repo.delete_thread(db, thread_id)
    log_event(logger, "thread_deleted", user_id=user.id, thread_id=thread_id)
    return {"deleted": True}
