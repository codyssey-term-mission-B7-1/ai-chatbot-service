"""비밀번호 해싱(bcrypt)·세션 바인딩용 지문 — 평문 저장 금지, 운영 전송에는 HTTPS 사용."""

import hashlib
import hmac

import bcrypt

from app.config import settings
from app.policies import MAX_PASSWORD_BYTES


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError("비밀번호는 UTF-8 기준 72바이트 이하여야 합니다.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# 이메일 존재 여부를 타이밍으로 누출하지 않기 위한 더미 해시(#72).
# 실제 계정 해시와 동일한 bcrypt 비용(기본 12 라운드)으로 미가입 경로의 소요 시간을 맞춘다.
_DUMMY_HASH = bcrypt.hashpw("timing-equalizer-not-a-real-account".encode("utf-8"), bcrypt.gensalt())


def verify_dummy_password(password: str) -> None:
    """존재하지 않는 이메일에도 실제 검증과 같은 bcrypt 연산을 수행한다.

    반환값은 항상 없다(검증 결과를 쓰지 않음). 로그인 실패 응답은 두 경로 모두 동일한 401이다.
    """
    try:
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)
    except ValueError:
        pass


def email_fingerprint(email: str) -> str:
    """세션-계정 바인딩(#33)용 지문. 쿠키에 이메일 평문을 넣지 않기 위해 HMAC으로 대체한다.

    키는 SESSION_SECRET — 시크릿을 모르는 쪽에서는 오프라인 대조로 이메일을 역산할 수 없다.
    """
    return hmac.new(
        settings.session_secret.encode("utf-8"), email.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:16]
