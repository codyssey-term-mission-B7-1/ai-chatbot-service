"""이메일 기반 비밀번호 재설정 — 토큰은 SHA-256 해시로만 저장, 단일 사용, 시간 제한 만료.

설계 원칙:
- 응답으로 계정 존재 여부를 누출하지 않는다(미가입 이메일도 동일한 202).
- 원문 토큰은 발송 메일에만 존재하고 DB에는 해시가 저장된다(유출 시 재현 불가).
- 완료 시 해당 계정의 기존 세션을 전부 폐기한다(#74 세션 폐기 재사용). 폐기 기준은
  1초 백오프를 둔다 — "재설정 직후 재로그인"이 같은 초 경합으로 거부되지 않게 한다.
  대가로 재설정과 같은 초에 발급된 구세션은 최대 1초 생존할 수 있다(실공격 가능성 무시 가능 수준,
  필요 시 scripts/revoke_sessions.py로 즉시 전량 폐기).
- 발송 수단은 Resend HTTPS API(resend_api_key)를 SMTP보다 우선 사용한다 — Railway
  Free/Hobby는 아웃바운드 SMTP 포트(25/465/587/2525)를 차단하므로(Pro만 허용),
  항상 열려 있는 443 HTTPS로 발송하는 Resend가 운영 기본 수단이다.
- SMTP 미설정 시: DEBUG=true면 재설정 링크를 서버 로그로만 출력(개발 편의),
  운영(DEBUG=false)이면 503으로 설정 누락을 알린다 — 설정 상태는 계정 정보가 아니므로
  누출에 해당하지 않는다.
"""

import hashlib
import logging
import secrets
import smtplib
import time
from email.message import EmailMessage

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import log_event
from app.models import PasswordReset, User
from app.services.security import hash_password
from app.services.sessions import revoke_user_sessions

logger = logging.getLogger("app.password_reset")

_EMAIL_SUBJECT = "AI Chatbot Service — 비밀번호 재설정 안내"


class SmtpNotConfigured(RuntimeError):
    """운영에서 이메일 발송 수단(SMTP 또는 Resend) 설정이 없어 메일을 보낼 수 없다."""


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_reset_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/reset-password?token={token}"


def create_reset_token(db: Session, user: User, request_ip: str = "") -> str | None:
    """요청 창 내 상한을 초과하면 None(메일 발송 생략). 정상이면 새 원문 토큰을 반환."""
    now = int(time.time())
    window_start = now - settings.password_reset_window_minutes * 60
    requested = db.scalar(
        select(func.count())
        .select_from(PasswordReset)
        .where(
            PasswordReset.user_id == user.id,
            PasswordReset.created_epoch >= window_start,
        )
    )
    if requested >= settings.password_reset_max_requests:
        log_event(
            logger,
            "auth_password_reset_rate_limited",
            user_id=user.id,
            level=logging.WARNING,
        )
        return None
    token = secrets.token_urlsafe(32)
    db.add(
        PasswordReset(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_epoch=now + settings.password_reset_expiry_minutes * 60,
            request_ip=request_ip[:64],
        )
    )
    db.commit()
    return token


def is_reset_token_valid(db: Session, token: str) -> bool:
    """GET 화면 표시용 비소모 검사 — 실제 사용은 complete_password_reset에서만."""
    if not token:
        return False
    row = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == _hash_token(token)))
    return row is not None and row.used_epoch is None and row.expires_epoch >= int(time.time())


def deliver_reset_email(to_email: str, link: str) -> str:
    """전송 결과: 'sent' | 'dev_console'. 발송 수단 미설정(운영)은 SmtpNotConfigured 예외.

    발송 수단 우선순위: Resend HTTPS API(resend_api_key) > SMTP(smtp_host).
    Railway Free/Hobby는 아웃바운드 SMTP 포트를 차단하므로 운영은 Resend 권장.
    동기 함수이므로 호출측(async 엔드포인트)은 asyncio.to_thread로 감싼다.
    """
    if settings.resend_api_key:
        _send_via_resend(to_email, link)
        return "sent"
    if settings.smtp_host:
        _send_via_smtp(to_email, link)
        return "sent"
    if settings.debug:
        logger.warning(
            "발송 수단 미설정(개발 모드) — 재설정 링크를 콘솔에 출력(운영은 발송 실패): %s",
            link,
        )
        return "dev_console"
    raise SmtpNotConfigured(
        "이메일 발송 설정(resend_api_key 또는 smtp_host)이 비어 있어 메일을 발송할 수 없습니다."
    )


def _reset_email_text(link: str) -> str:
    """SMTP 본문과 Resend text가 같은 문안을 쓰도록 한 곳에 모은다."""
    return f"""안녕하세요, AI Chatbot Service입니다.

비밀번호 재설정 요청을 받았습니다. 아래 링크에서 새 비밀번호를 설정하세요.
({settings.password_reset_expiry_minutes}분 후 만료되며 한 번만 사용할 수 있습니다.)

{link}

본인이 요청하지 않았다면 이 메일을 무시하세요 — 기존 비밀번호는 그대로 유지됩니다.
링크를 누른 적이 없다면 계정에 접근한 사람이 없을 가능성이 높지만,
혹시 걱정된다면 로그인 후 비밀번호를 직접 변경하고 관리자에게 알려주세요.
"""


def _send_via_resend(to_email: str, link: str) -> None:
    """Resend HTTPS API 발송 — Railway Free/Hobby에서도 443은 항상 허용된다.

    도메인 인증 전 기본 발신자(onboarding@resend.dev)는 수신이 Resend 계정 본인
    이메일로 제한된다. 실패 시 키·원문 노출 없이 상태코드만 담아 예외(라우트가 502 변환).
    """
    response = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.resend_from,
            "to": [to_email],
            "subject": _EMAIL_SUBJECT,
            "text": _reset_email_text(link),
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Resend API 발송 실패: HTTP {response.status_code}")


def _send_via_smtp(to_email: str, link: str) -> None:
    """기존 smtplib 발송 경로 — Railway Pro가 아니면 아웃바운드 SMTP 포트가 차단된다."""
    message = EmailMessage()
    message["Subject"] = _EMAIL_SUBJECT
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message.set_content(_reset_email_text(link))
    if settings.smtp_port == 465:
        smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
    else:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    with smtp:
        if settings.smtp_port != 465:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


def complete_password_reset(db: Session, token: str, new_password: str) -> User | None:
    """토큰 검증 → 비밀번호 교체 → 토큰 소모 → 기존 세션 전부 폐기. 실패 시 None.

    비밀번호 정책 검증은 스키마(PasswordResetCompleteIn)에서 이미 수행했다.
    """
    row = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == _hash_token(token)))
    if row is None or row.used_epoch is not None or row.expires_epoch < int(time.time()):
        return None
    user = db.get(User, row.user_id)
    if user is None:
        return None
    user.password_hash = hash_password(new_password)
    row.used_epoch = int(time.time())
    db.commit()
    # 탈취된 세션까지 무효화하되 1초 백오프 — 같은 초에 몰린 재로그인이 거부되지 않게(#78 교훈).
    # 재설정 이전에 발급된 세션(iat <= 기준-1)은 전부 폐기된다.
    revoke_user_sessions(db, user, backoff_seconds=1)
    return user
