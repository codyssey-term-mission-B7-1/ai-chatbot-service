"""회원 인증 API — 가입/로그인/로그아웃/내 정보."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.logging_config import log_event
from app.models import User
from app.schemas import LoginIn, SignupIn, UserOut
from app.services.security import hash_password, verify_password

logger = logging.getLogger("app.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             summary="회원가입",
             description="이메일/비밀번호로 계정 생성. 비밀번호는 bcrypt로 해싱되어 저장됩니다.",
             responses={409: {"description": "이미 가입된 이메일"},
                        422: {"description": "입력 검증 실패 (이메일 형식·비밀번호 8자 미만)"}})
def signup(body: SignupIn, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.email == body.email).first()
    if exists:
        raise HTTPException(status_code=409, detail="이미 가입된 이메일이에요.")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        nickname=body.nickname,
    )
    db.add(user)
    db.commit()
    log_event(logger, "user_signup", user_id=user.id, email_domain=body.email.split("@")[-1])
    return UserOut(email=user.email, nickname=user.nickname)


@router.post("/login", response_model=UserOut,
             summary="로그인",
             description="세션 쿠키를 발급합니다. 이후 요청에 쿠키를 실어 보내세요.",
             responses={401: {"description": "이메일 또는 비밀번호 불일치"}})
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        # 사용자 존재 여부를 드러내지 않는 통일 메시지
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않아요.")

    request.session["user_id"] = user.id  # 세션 쿠키 발급
    log_event(logger, "user_login", user_id=user.id)
    return UserOut(email=user.email, nickname=user.nickname)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"detail": "로그아웃했어요."}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(email=user.email, nickname=user.nickname)
