"""회원 인증 API. 세션 쿠키 발급과 앱 관리자 권한은 별개다."""

import asyncio
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.logging_config import log_event
from app.models import User
from app.repositories.users import DuplicateEmailError, create_user, find_by_email
from app.schemas import LoginIn, PasswordResetCompleteIn, PasswordResetRequestIn, SignupIn, UserOut
from app.services.admin import is_admin
from app.services.password_reset import (
    SmtpNotConfigured,
    build_reset_link,
    complete_password_reset,
    create_reset_token,
    deliver_reset_email,
)
from app.services.rate_limit import (
    client_ip,
    login_limiter,
    password_reset_ip_limiter,
    retry_after_hint,
    signup_ip_limiter,
)
from app.services.security import (
    email_fingerprint,
    hash_password,
    is_peppered_hash,
    mark_peppered_hash,
    verify_dummy_password,
    verify_password,
    verify_password_legacy,
)

logger = logging.getLogger("app.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
    description="페퍼(HMAC) + bcrypt 해싱. 8~64자, UTF-8 72바이트 이하, 공백만으로 구성 불가.",
    responses={
        409: {"description": "이미 가입된 이메일"},
        422: {"description": "이메일/비밀번호/닉네임 검증 실패"},
    },
)
def signup(body: SignupIn, request: Request, db: Session = Depends(get_db)):
    # IP 기반 회원가입 상한 — 봇 대량 계정 생성 최소 방어. CAPTCHA/이메일 인증은 다음 마일스톤.
    ip = client_ip(request)
    retry = signup_ip_limiter.try_acquire(f"ip:{ip}")
    if retry > 0:
        log_event(
            logger,
            "signup_rate_limited",
            ip_hash=ip[:16],
            retry_after_sec=retry,
            level=logging.WARNING,
        )
        raise HTTPException(
            status_code=429,
            detail=(
                f"짧은 시간에 너무 많은 계정을 만들었어요. "
                f"{retry_after_hint(retry)} 다시 시도해 주세요."
            ),
            headers={"Retry-After": str(retry)},
        )
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
            detail=(
                f"로그인 시도가 많아 일시적으로 잠겼어요. "
                f"{retry_after_hint(retry_after)} 다시 시도해 주세요."
            ),
            headers={"Retry-After": str(retry_after)},
        )
    user = find_by_email(db, body.email)
    if user is not None:
        password_ok = verify_password(body.password, user.password_hash)
        if not password_ok:
            # 페퍼 도입 전 레거시 해시 — 검증되면 즉시 페퍼 적용 해시로 재저장(투명 마이그레이션).
            if verify_password_legacy(body.password, user.password_hash):
                user.password_hash = hash_password(body.password)
                db.commit()
                log_event(logger, "auth_password_rehashed", user_id=user.id)
                password_ok = True
        elif not is_peppered_hash(user.password_hash):
            # 마커 도입 직후 창구에 저장된 비표시 페퍼 해시 — 마킹만 보강한다.
            user.password_hash = mark_peppered_hash(user.password_hash)
            db.commit()
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
    request.session["iat"] = int(time.time())  # 서버 측 폐기(#74) 기준이 되는 발급 시각
    request.state.authenticated_user_id = user.id
    log_event(logger, "user_login", user_id=user.id)
    return UserOut(email=user.email, nickname=user.nickname, is_admin=is_admin(db, user))


@router.post(
    "/password/reset-request",
    status_code=status.HTTP_202_ACCEPTED,
    summary="비밀번호 재설정 요청",
    description=(
        "입력한 이메일이 가입되어 있으면 재설정 링크를 담은 메일을 보낸다. "
        "계정 존재 여부를 응답으로 구분할 수 없게 항상 같은 202를 반환한다. "
        "요청 상한(PASSWORD_RESET_MAX_REQUESTS회/PASSWORD_RESET_WINDOW_MINUTES분)을 넘으면 "
        "메일을 보내지 않지만 응답은 동일하다. 운영에서 SMTP 미설정이면 503."
    ),
    responses={
        202: {"description": "요청 접수 — 이메일 존재 여부는 알려주지 않음"},
        503: {"description": "메일 발송(SMTP) 미설정 — 운영자가 SMTP_* 환경변수를 등록해야 함"},
        502: {"description": "메일 발송 실패"},
    },
)
async def password_reset_request(
    body: PasswordResetRequestIn, request: Request, db: Session = Depends(get_db)
):
    generic_ok = {"detail": "요청을 받았어요. 이메일이 가입되어 있다면 재설정 안내를 보냈습니다."}
    # IP 기반 상한 — 분당 N회로 메일 폭탄/계정 존재 열거 속도를 늦춘다.
    ip = client_ip(request)
    ip_retry = password_reset_ip_limiter.try_acquire(f"ip:{ip}")
    if ip_retry > 0:
        log_event(
            logger,
            "auth_password_reset_ip_rate_limited",
            ip_hash=ip[:16],
            retry_after_sec=ip_retry,
            level=logging.WARNING,
        )
        raise HTTPException(
            status_code=429,
            detail=f"요청이 너무 잦아요. {retry_after_hint(ip_retry)} 다시 시도해 주세요.",
            headers={"Retry-After": str(ip_retry)},
        )
    user = find_by_email(db, body.email)
    if user is None:
        # 타이밍 평탄화(#72와 동일 원칙) — 미가입 경로도 bcrypt 비용을 지불한다.
        verify_dummy_password("timing-equalizer")
        return generic_ok
    token = create_reset_token(db, user, request.client.host if request.client else "")
    if token is None:  # 요청 상한 초과 — 응답은 동일하게 유지(존재 누출 방지)
        return generic_ok
    log_event(logger, "auth_password_reset_requested", user_id=user.id)
    link = build_reset_link(str(request.base_url), token)
    try:
        # 동기 smtplib을 이벤트 루프 밖에서 실행 — 다른 요청을 차단하지 않는다.
        result = await asyncio.to_thread(deliver_reset_email, user.email, link)
    except SmtpNotConfigured:
        log_event(logger, "auth_password_reset_email_unconfigured", level=logging.WARNING)
        raise HTTPException(
            status_code=503,
            detail=(
                "메일 발송 설정(SMTP)이 되어 있지 않아 요청을 처리할 수 없어요. "
                "운영자에게 문의해 주세요."
            ),
        ) from None
    except Exception as exc:  # SMTP 연결/인증 오류 — 토큰은 만료되어 자연 무효화된다.
        # Resend 응답 body나 SMTP trace에 발송 API 키부·토큰이 포함될 수 있어
        # 예외 타입만 기록해 원문 누출을 막는다(#104와 동일 원칙).
        log_event(
            logger,
            "auth_password_reset_email_failed",
            error=type(exc).__name__,
            level=logging.ERROR,
        )
        raise HTTPException(
            status_code=502, detail="재설정 메일 발송에 실패했어요. 잠시 후 다시 시도해 주세요."
        ) from None
    if result == "dev_console":
        event_name = "auth_password_reset_email_dev_console"
    else:
        event_name = "auth_password_reset_email_sent"
    log_event(logger, event_name, user_id=user.id)
    return generic_ok


@router.post(
    "/password/reset",
    summary="비밀번호 재설정 완료",
    description=(
        "메일 링크의 토큰과 새 비밀번호로 재설정을 완료한다. 토큰은 단일 사용·시간 제한이며 "
        "완료 시 해당 계정의 기존 세션을 전부 폐기한다(다른 기기 로그아웃)."
    ),
    responses={
        200: {"description": "변경 완료 — 새 비밀번호로 로그인 필요"},
        400: {"description": "유효하지 않거나 만료/사용된 토큰"},
    },
)
def password_reset(body: PasswordResetCompleteIn, db: Session = Depends(get_db)):
    user = complete_password_reset(db, body.token, body.new_password)
    if user is None:
        log_event(logger, "auth_password_reset_rejected", level=logging.WARNING)
        raise HTTPException(
            status_code=400,
            detail="재설정 링크가 유효하지 않거나 만료되었어요. 다시 요청해 주세요.",
        )
    log_event(logger, "auth_password_reset_completed", user_id=user.id)
    return {"detail": "비밀번호를 변경했어요. 새 비밀번호로 로그인해 주세요."}


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
