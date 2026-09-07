"""비밀번호 해싱(bcrypt)·세션 바인딩용 지문 — 평문 저장/전송 금지."""
import hashlib
import hmac

import bcrypt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def email_fingerprint(email: str) -> str:
    """세션-계정 바인딩(#33)용 지문. 쿠키에 이메일 평문을 넣지 않기 위해 HMAC으로 대체한다.

    키는 SESSION_SECRET — 시크릿을 모르는 쪽에서는 오프라인 대조로 이메일을 역산할 수 없다.
    """
    return hmac.new(
        settings.session_secret.encode("utf-8"), email.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:16]
