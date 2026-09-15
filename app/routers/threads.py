"""대화 스레드(thread) API — 목록·생성·단건 조회·삭제·스레드별 기록(중첩)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.audit import E
from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.logging_config import log_event
from app.models import User
from app.policies import DEFAULT_PAGE_SIZE
from app.repositories import threads as threads_repo
from app.repositories.chat_logs import list_logs
from app.schemas import ChatLogOut, LogStatus, ThreadOut

logger = logging.getLogger("app.threads")
router = APIRouter(prefix="/api/thread", tags=["threads"])
rest_router = APIRouter(prefix="/api/threads", tags=["threads"])


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
    log_event(logger, E.THREAD_CREATED, user_id=user.id, thread_id=thread.id)
    return thread


@router.get(
    "/list",
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


@router.get(
    "/{thread_id}",
    response_model=ThreadOut,
    summary="대화 단건 조회",
    description="내 대화 하나. 남의 대화·없는 대화는 404.",
    responses={
        401: {"description": "로그인 필요"},
        404: {"description": "존재하지 않거나 내 대화가 아님"},
    },
)
def get_thread(
    thread_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thread = threads_repo.get_thread(db, thread_id, user_id=user.id)
    if thread is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없어요.")
    return thread


@router.delete(
    "/{thread_id}",
    status_code=204,
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
    log_event(logger, E.THREAD_DELETED, user_id=user.id, thread_id=thread_id)
    return Response(status_code=204)


@router.get(
    "/{thread_id}/chats",
    response_model=list[ChatLogOut],
    summary="대화별 기록 조회",
    description="그 대화의 기록만 최신순. limit은 1~200. 남의 대화는 404.",
    responses={
        401: {"description": "로그인 필요"},
        404: {"description": "존재하지 않거나 내 대화가 아님"},
    },
)
def thread_chats(
    thread_id: int,
    limit: int = DEFAULT_PAGE_SIZE,
    status_: LogStatus | None = Query(default=None, alias="status"),
    before_id: int | None = Query(default=None, gt=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if threads_repo.get_thread(db, thread_id, user_id=user.id) is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없어요.")
    return list_logs(
        db, user_id=user.id, limit=limit, status=status_, before_id=before_id, thread_id=thread_id
    )


@rest_router.post(
    "",
    response_model=ThreadOut,
    status_code=201,
    summary="새 대화 시작 (REST 표준)",
    description="빈 기록의 새 대화(스레드)를 만든다. 사용자는 상한(기본 100)까지 만들 수 있다.",
    responses={
        401: {"description": "로그인 필요"},
        409: {"description": "대화 수 상한 도달"},
    },
)
def create_thread_rest(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_thread(user=user, db=db)


@rest_router.get(
    "",
    response_model=list[ThreadOut],
    summary="내 대화 목록 (REST 표준)",
    description="최근 활동순(수정 시각 내림차순) 최대 50개. title이 없으면 '기본 대화'.",
    responses={401: {"description": "로그인 필요"}},
)
def list_my_threads_rest(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_my_threads(user=user, db=db)


@rest_router.get(
    "/{thread_id}",
    response_model=ThreadOut,
    summary="대화 단건 조회 (REST 표준)",
    description="내 대화 하나. 남의 대화·없는 대화는 404.",
    responses={
        401: {"description": "로그인 필요"},
        404: {"description": "존재하지 않거나 내 대화가 아님"},
    },
)
def get_thread_rest(
    thread_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_thread(thread_id=thread_id, user=user, db=db)


@rest_router.delete(
    "/{thread_id}",
    status_code=204,
    summary="대화 삭제 (REST 표준)",
    description="대화와 그 안의 기록을 함께 삭제한다. 남의 대화는 404.",
    responses={
        401: {"description": "로그인 필요"},
        404: {"description": "존재하지 않거나 내 대화가 아님"},
    },
)
def delete_my_thread_rest(
    thread_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return delete_my_thread(thread_id=thread_id, user=user, db=db)


@rest_router.get(
    "/{thread_id}/chats",
    response_model=list[ChatLogOut],
    summary="대화별 기록 조회 (REST 표준)",
    description="그 대화의 기록만 최신순. limit은 1~200. 남의 대화는 404.",
    responses={
        401: {"description": "로그인 필요"},
        404: {"description": "존재하지 않거나 내 대화가 아님"},
    },
)
def thread_chats_rest(
    thread_id: int,
    limit: int = DEFAULT_PAGE_SIZE,
    status_: LogStatus | None = Query(default=None, alias="status"),
    before_id: int | None = Query(default=None, gt=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return thread_chats(
        thread_id=thread_id,
        limit=limit,
        status_=status_,
        before_id=before_id,
        user=user,
        db=db,
    )
