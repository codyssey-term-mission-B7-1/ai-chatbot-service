"""회원 인증 API. 세션 쿠키 발급과 앱 관리자 권한은 별개다."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.logging_config import log_event
from app.models import User
from app.repositories.users import DuplicateEmailError, create_user, find_by_email
from app.schemas import LoginIn, SignupIn, UserOut
from app.services.admin import is_admin
from app.services.rate_limit import login_limiter
from app.services.security import (
    email_fingerprint,
    hash_password,
    verify_dummy_password,
    verify_password,
)

logger = logging.getLogger("app.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
    description="bcrypt 해싱. 8~64자 및 UTF-8 72바이트 이하.",
    responses={
        409: {"description": "이미 가입된 이메일"},
        422: {"description": "이메일/비밀번호/닉네임 검증 실패"},
    },
)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    try:
        user = create_user(
            db, email=body.email, password_hash=hash_password(body.password), nickname=body.nickname
        )
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail="이미 가입된 이메일이에요.") from None
    log_event(logger, "user_signup", user_id=user.id, email_domain=body.email.split("@")[-1])
    return UserOut(email=user.email, nickname=user.nickname, is_admin=False)


@router.post(
    "/login",
    response_model=UserOut,
    summary="로그인",
    description=(
        "서명된 세션 쿠키를 발급합니다. JWT가 아닙니다. "
        "이메일별 실패 누적 잠금(LOGIN_MAX_FAILS회/LOGIN_LOCKOUT_SEC초)이 있어 초과 시 429입니다."
    ),
    responses={
        401: {"description": "이메일 또는 비밀번호 불일치"},
        429: {"description": "반복 실패로 일시 잠금. Retry-After 헤더 참고"},
    },
)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    # 무차별 대입 방어(#72): 이메일별 실패 누적 — 잠금 중에는 올바른 비밀번호도 거부한다.
    retry_after = login_limiter.blocked_for(body.email)
    if retry_after > 0:
        log_event(
            logger,
            "user_login_locked",
            email_domain=body.email.split("@")[-1],
            retry_after_sec=retry_after,
            level=logging.WARNING,
        )
        raise HTTPException(
            status_code=429,
            detail="로그인 시도가 많아 일시적으로 잠겼어요. 잠시 후 다시 시도해 주세요.",
            headers={"Retry-After": str(retry_after)},
        )
    user = find_by_email(db, body.email)
    if user is not None:
        password_ok = verify_password(body.password, user.password_hash)
    else:
        # 이메일 존재 여부를 타이밍으로 누출하지 않게 미가입 경로도 bcrypt를 수행한다(#72).
        verify_dummy_password(body.password)
        password_ok = False
    if not password_ok:
        login_limiter.record(body.email)
        log_event(
            logger,
            "user_login_fail",
            user_id=user.id if user is not None else None,
            email_domain=body.email.split("@")[-1],
            level=logging.WARNING,
        )
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않아요.")
    login_limiter.clear(body.email)
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["email_fp"] = email_fingerprint(user.email)
    request.state.authenticated_user_id = user.id
    log_event(logger, "user_login", user_id=user.id)
    return UserOut(email=user.email, nickname=user.nickname, is_admin=is_admin(db, user))


@router.post(
    "/logout",
    summary="로그아웃",
    description="현재 클라이언트의 세션 쿠키를 비웁니다. 비로그인도 200입니다.",
)
def logout(request: Request):
    request.session.clear()
    return {"detail": "로그아웃했어요."}


@router.get(
    "/me",
    response_model=UserOut,
    summary="내 정보",
    description="현재 계정 정보와 앱 관리자 권한 여부를 반환합니다.",
)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return UserOut(email=user.email, nickname=user.nickname, is_admin=is_admin(db, user))
