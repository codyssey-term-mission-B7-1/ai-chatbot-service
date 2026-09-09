"""페퍼(PASSWORD_PEPPER) + bcrypt 보안 계약 — 해싱 구조·레거시 마이그레이션·운영 게이트."""

import bcrypt
import pytest

from app.config import resolve_password_pepper
from app.services.security import (
    hash_password,
    is_peppered_hash,
    mark_peppered_hash,
    verify_dummy_password,
    verify_password,
    verify_password_legacy,
)


def test_hash_contains_random_salt_per_password():
    """bcrypt gensalt() — 같은 비밀번호도 매번 다른 해시(무지개 테이븑 방어)."""
    a = hash_password("UserPass123!")
    b = hash_password("UserPass123!")
    assert a != b
    assert a.startswith("p2:$2")  # 페퍼 마커 + bcrypt 형식
    assert is_peppered_hash(a)


def test_verify_roundtrip_current_path():
    h = hash_password("UserPass123!")
    assert verify_password("UserPass123!", h) is True
    assert verify_password("wrong-password", h) is False


def test_pepper_is_applied_to_hash():
    """해시는 페퍼 적용 값이어야 한다 — 평문 bcrypt와 호환되면 안 된다."""
    plain_bcrypt = bcrypt.hashpw("UserPass123!".encode(), bcrypt.gensalt()).decode()
    # 평문 bcrypt 해시는 현재 경로에서 검증되지 않는다(레거시 전용)
    assert verify_password("UserPass123!", plain_bcrypt) is False
    assert verify_password_legacy("UserPass123!", plain_bcrypt) is True


def test_legacy_hash_verifies_on_legacy_path_only():
    """레거시 해시 — 레거시 경로로만 검증된다(로그인 마이그레이션에서 사용)."""
    legacy_hash = bcrypt.hashpw("UserPass123!".encode(), bcrypt.gensalt()).decode()
    assert verify_password_legacy("UserPass123!", legacy_hash) is True
    assert verify_password_legacy("nope", legacy_hash) is False


def test_rehashed_legacy_becomes_current():
    """레거시 해시를 hash_password로 재저장하면 현재 경로로 검증된다(투명 마이그레이션)."""
    password = "UserPass123!"
    user_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()  # 페퍼 이전 값
    if verify_password_legacy(password, user_hash):
        user_hash = hash_password(password)  # 로그인 라우트가 수행하는 재해싱
    assert verify_password(password, user_hash) is True


def test_verify_password_tolerates_malformed_hash():
    assert verify_password("x", "not-a-bcrypt-hash") is False
    assert verify_password_legacy("x", "not-a-bcrypt-hash") is False


def test_dummy_verification_never_raises():
    verify_dummy_password("whatever")  # 예외 없이 통과해야 한다


def test_pepper_quality_gate_production_rejects_missing():
    """운영(debug=False)에서 빈/짧은/공개 페퍼는 시작을 거부한다."""
    with pytest.raises(RuntimeError, match="PASSWORD_PEPPER"):
        resolve_password_pepper("", debug=False)
    with pytest.raises(RuntimeError, match="PASSWORD_PEPPER"):
        resolve_password_pepper("short", debug=False)
    with pytest.raises(RuntimeError, match="PASSWORD_PEPPER"):
        resolve_password_pepper("change-me", debug=False)


def test_pepper_quality_gate_dev_substitutes():
    """개발(debug=True)은 임시 페퍼로 대체한다(32자 이상)."""
    substituted = resolve_password_pepper("", debug=True)
    assert len(substituted) >= 32


def test_pepper_quality_gate_accepts_strong_value():
    strong = "a" * 48
    assert resolve_password_pepper(strong, debug=False) == strong


def test_byte_limit_guard_still_enforced():
    """UTF-8 72바이트 상한 가드는 그대로 — HMAC이 안전하게 만들어도 API 계약(422)과 일치."""
    with pytest.raises(ValueError, match="72바이트"):
        hash_password("가" * 40)  # 120 UTF-8 바이트


def test_marker_is_attached_and_strippable():
    """p2: 마커 — 새 해시에 붙고, 마커 없는 페퍼 해시에는 보강 마킹이 가능하다."""
    h = hash_password("UserPass123!")
    assert is_peppered_hash(h)
    raw = h[len("p2:") :]  # 마커 없는 형태(마커 도입 직후 창구 호환)
    assert not is_peppered_hash(raw)
    assert verify_password("UserPass123!", raw) is True  # 마커 없이도 검증 호환
    assert mark_peppered_hash(raw) == h.split("$", 1)[0] + raw or mark_peppered_hash(raw).endswith(
        raw
    )
    assert is_peppered_hash(mark_peppered_hash(raw))


def test_legacy_hash_is_not_peppered_hash():
    """레거시 평문 bcrypt 해시는 p2: 마커가 없다(현황 집계의 레거시 분류 근거)."""
    legacy = bcrypt.hashpw(b"UserPass123!", bcrypt.gensalt()).decode()
    assert not is_peppered_hash(legacy)
