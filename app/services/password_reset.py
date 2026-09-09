"""이메일 기반 비밀번호 재설정 — 토큰은 SHA-256 해시로만 저장, 단일 사용, 시간 제한 만료.

설계 원칙:
- 응답으로 계정 존재 여부를 누출하지 않는다(미가입 이메일도 동일한 202).
- 원문 토큰은 발송 메일에만 존재하고 DB에는 해시가 저장된다(유출 시 재현 불가).
- 완료 시 해당 계정의 기존 세션을 전부 폐기한다(#74 세션 폐기 재사용). 폐기 기준은
  1초 백오프를 둔다 — "재설정 직후 재로그인"이 같은 초 경합으로 거부되지 않게 한다.
  대가로 재설정과 같은 초에 발급된 구세션은 최대 1초 생존할 수 있다(실공격 가능성 무시 가능 수준,
  필요 시 scripts/revoke_sessions.py로 즉시 전량 폐기).
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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import log_event
from app.models import PasswordReset, User
from app.services.security import hash_password
from app.services.sessions import revoke_user_sessions

logger = logging.getLogger("app.password_reset")


class SmtpNotConfigured(RuntimeError):
    """운영에서 SMTP 설정이 없어 메일을 보낼 수 없다."""


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_reset_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/reset-password?token={token}"


def create_reset_token(db: Session, user: User, request_ip: str = "") -> str | None:
    """요청 창 내 상한을 초과하면 None(메일 발송 생략). 정상이면 새 원문 토큰을 반환."""
    now = int(time.time())
    window_start = now - settings.password_reset_window_minutes * 60
    requested = db.scalar(
        select(func.count()).select_from(PasswordReset).where(
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
    """전송 결과: 'sent' | 'dev_console'. SMTP 미설정(운영)은 SmtpNotConfigured 예외.

    동기 smtplib이므로 호출측(async 엔드포인트)은 asyncio.to_thread로 감싼다.
    """
    if not settings.smtp_host:
        if settings.debug:
            logger.warning(
                "SMTP 미설정(개발 모드) — 재설정 링크를 콘솔에 출력합니다(운영은 발송 실패): %s",
                link,
            )
            return "dev_console"
        raise SmtpNotConfigured("SMTP 설정(smtp_host)이 비어 있어 메일을 발송할 수 없습니다.")

    message = EmailMessage()
    message["Subject"] = "AI Chatbot Service — 비밀번호 재설정 안내"
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message.set_content(
        f"""안녕하세요, AI Chatbot Service입니다.

비밀번호 재설정 요청을 받았습니다. 아래 링크에서 새 비밀번호를 설정하세요.
({settings.password_reset_expiry_minutes}분 후 만료되며 한 번만 사용할 수 있습니다.)

{link}

본인이 요청하지 않았다면 이 메일을 무시하세요 — 기존 비밀번호는 그대로 유지됩니다.
링크를 누른 적이 없다면 계정에 접근한 사람이 없을 가능성이 높지만,
혹시 걱정된다면 로그인 후 비밀번호를 직접 변경하고 관리자에게 알려주세요.
"""
    )
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
    return "sent"


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
