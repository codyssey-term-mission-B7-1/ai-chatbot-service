"""비밀번호 해싱(peppered bcrypt)·세션 바인딩용 지문 — 평문 저장 금지, 운영 전송에는 HTTPS 사용."""

import hashlib
import hmac

import bcrypt

from app.config import settings
from app.policies import MAX_PASSWORD_BYTES


def _peppered(password: str) -> bytes:
    """비밀번호를 페퍼로 HMAC 변환한다. 출력 32바이트 고정."""
    return hmac.new(
        settings.password_pepper.encode("utf-8"), password.encode("utf-8"), hashlib.sha256
    ).digest()


PEPPER_MARK = "p2:"


def hash_password(password: str) -> str:
    """페퍼 적용 bcrypt 해시(p2: 마커 포함). 신규 가입·재설정·마이그레이션이 모두 이 경로를 쓴다."""
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError("비밀번호는 UTF-8 기준 72바이트 이하여야 합니다.")
    digest = bcrypt.hashpw(_peppered(password), bcrypt.gensalt()).decode("utf-8")
    return PEPPER_MARK + digest


def is_peppered_hash(password_hash: str) -> bool:
    """저장된 해시가 페퍼 적용(p2: 마커)인지 — 관리자 현황 조회용."""
    return password_hash.startswith(PEPPER_MARK)


def mark_peppered_hash(password_hash: str) -> str:
    """마커 없는 페퍼 해시(마커 도입 전 창구에 저장된 값)에 마커를 붙인다."""
    return password_hash if is_peppered_hash(password_hash) else PEPPER_MARK + password_hash


def _strip_mark(password_hash: str) -> str:
    return password_hash[len(PEPPER_MARK) :] if is_peppered_hash(password_hash) else password_hash


def verify_password(password: str, password_hash: str) -> bool:
    """페퍼 적용 해시 검증(현재 기본 경로). 마커 유무와 무관하게 동작한다."""
    try:
        return bcrypt.checkpw(_peppered(password), _strip_mark(password_hash).encode("utf-8"))
    except ValueError:
        return False


def verify_password_legacy(password: str, password_hash: str) -> bool:
    """페퍼 도입 전 평문 bcrypt 해시 검증(마이그레이션 전용)."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), _strip_mark(password_hash).encode("utf-8"))
    except ValueError:
        return False


_DUMMY_HASH = bcrypt.hashpw(_peppered("timing-equalizer-not-a-real-account"), bcrypt.gensalt())


def verify_dummy_password(password: str) -> None:
    """존재하지 않는 이메일에도 실제 검증과 같은 bcrypt 연산을 수행한다."""
    try:
        bcrypt.checkpw(_peppered(password), _DUMMY_HASH)
    except ValueError:
        pass


def email_fingerprint(email: str) -> str:
    """세션-계정 바인딩(#33)용 지문. 쿠키에 이메일 평문을 넣지 않기 위해 HMAC으로 대체한다."""
    return hmac.new(
        settings.session_secret.encode("utf-8"), email.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:16]
