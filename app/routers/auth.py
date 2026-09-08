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
from app.services.security import email_fingerprint, hash_password, verify_password

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
    description="서명된 세션 쿠키를 발급합니다. JWT가 아닙니다.",
    responses={401: {"description": "이메일 또는 비밀번호 불일치"}},
)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = find_by_email(db, body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않아요.")
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
