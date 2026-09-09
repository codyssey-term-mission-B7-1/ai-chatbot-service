"""비밀번호 해싱(peppered bcrypt)·세션 바인딩용 지문 — 평문 저장 금지, 운영 전송에는 HTTPS 사용.

해싱 구조(2026-09 강화):
1. 페퍼(PASSWORD_PEPPER) — 서버 비밀값으로 모든 비밀번호에 공통 적용. DB가 유출돼도
   페퍼를 모르면 오프라인 대조 불가. HMAC-SHA256(pepper, password)로 먼저 변환한다.
2. bcrypt — 검증된 느린 해시. gensalt()가 비밀번호마다 무작위 솔트를 생성하므로
   동일 비밀번호도 해시가 매번 다르고 무지개 테이블 대조도 막힌다.
   HMAC 출력은 32바이트 고정이라 bcrypt의 UTF-8 72바이트 한계를 자동으로 만족한다.

기존(페퍼 이전) 해시를 가진 계정은 로그인 시 레거시 경로로 검증된 뒤
페퍼 적용 해시로 즉시 재저장된다(투명 마이그레이션 — auth.py 참조).

해시 버전 마커: 페퍼 적용 해시는 "p2:" 접두어로 저장한다. 접두어가 없으면
페퍼 이전(또는 마커 도입 직후의 비표시 페퍼 해시)이다. 검증은 두 형식을 모두
수용하므로 마커는 하위 호환을 깨뜨리지 않으며, 관리자 현황 조회
(GET /api/admin/security/password-hashes)가 마이그레이션 진행률을 정확히
보고할 수 있게 해 준다.
"""

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


PEPPER_MARK = "p2:"  # 페퍼 적용 해시임을 나타내는 저장 버전 마커


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
    """마커 없는 페퍼 해시(마커 도입 전 창구에 저장된 값)에 마커를 붙인다.

    검증은 마커 없이도 되지만, 마킹해야 마이그레이션 현황이 정확해진다.
    """
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
    """페퍼 도입 전 평문 bcrypt 해시 검증(마이그레이션 전용).

    로그인에서 verify_password 실패 시에만 시도한다. 전 계정이 재로그인으로
    재해싱되면 이 경로는 제거할 수 있다(docs/OPERATIONS.md 참조).
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), _strip_mark(password_hash).encode("utf-8"))
    except ValueError:
        return False


# 이메일 존재 여부를 타이밍으로 누출하지 않기 위한 더미 해시(#72).
# 실제 계정 해시와 동일한 bcrypt 비용(기본 12 라운드)으로 미가입 경로의 소요 시간을 맞춘다.
# 현재 기본 경로가 페퍼 적용 해시이므로 더미도 페퍼 적용 값으로 생성한다.
_DUMMY_HASH = bcrypt.hashpw(_peppered("timing-equalizer-not-a-real-account"), bcrypt.gensalt())


def verify_dummy_password(password: str) -> None:
    """존재하지 않는 이메일에도 실제 검증과 같은 bcrypt 연산을 수행한다.

    반환값은 항상 없다(검증 결과를 쓰지 않음). 로그인 실패 응답은 두 경로 모두 동일한 401이다.
    """
    try:
        bcrypt.checkpw(_peppered(password), _DUMMY_HASH)
    except ValueError:
        pass


def email_fingerprint(email: str) -> str:
    """세션-계정 바인딩(#33)용 지문. 쿠키에 이메일 평문을 넣지 않기 위해 HMAC으로 대체한다.

    키는 SESSION_SECRET — 시크릿을 모르는 쪽에서는 오프라인 대조로 이메일을 역산할 수 없다.
    """
    return hmac.new(
        settings.session_secret.encode("utf-8"), email.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:16]
