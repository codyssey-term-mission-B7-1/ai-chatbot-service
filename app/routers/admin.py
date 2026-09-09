"""관리자 전용 기능 — 전체 대화 조회·해시 현황·사용자 삭제. 권한은 서버 CLI로만 부여한다."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_admin_user
from app.logging_config import log_event
from app.models import User
from app.policies import MAX_LOG_PAGE_SIZE
from app.repositories.chat_logs import list_logs
from app.schemas import (
    AdminChatLogOut,
    AdminLogPage,
    DeletedUserOut,
    LogStatus,
    PasswordHashStatusOut,
)
from app.services.admin import is_admin
from app.services.security import is_peppered_hash
from app.services.sessions import revoke_user_sessions

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
        "admin_hash_status_viewed",
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
        "admin_user_deleted",
        user_id=user.id,
        deleted_user_id=deleted_id,
        email_domain=deleted_email.split("@")[-1],
        level=logging.WARNING,
    )
    return DeletedUserOut(user_id=deleted_id, email=deleted_email)
