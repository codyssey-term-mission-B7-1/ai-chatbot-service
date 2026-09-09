"""유닛 테스트 — 서버 측 세션 폐기(#74)."""

import time

from app.models import User
from app.services.security import hash_password
from app.services.sessions import is_session_revoked, revoke_sessions_by_email, revoke_user_sessions


def _user(db, email="revoke@test.com"):
    user = User(email=email, password_hash=hash_password("pw12345"), nickname="테스트")
    db.add(user)
    db.commit()
    return user


def test_no_revocation_row_means_active(db):
    user = _user(db)
    assert is_session_revoked(db, user.id, 0) is False


def test_revocation_invalidates_sessions_issued_before_or_at_epoch(db):
    user = _user(db)
    epoch = revoke_user_sessions(db, user)
    assert is_session_revoked(db, user.id, iat=epoch) is True  # 같은 초 발급도 폐기
    assert is_session_revoked(db, user.id, iat=epoch - 1) is True
    assert is_session_revoked(db, user.id, iat=epoch + 1) is False  # 이후 재로그인은 통과


def test_re_revocation_updates_the_epoch(db):
    user = _user(db)
    first = revoke_user_sessions(db, user)
    time.sleep(0.01)
    second = revoke_user_sessions(db, user)
    assert second >= first
    assert is_session_revoked(db, user.id, second) is True
    assert is_session_revoked(db, user.id, first) is True


def test_missing_iat_is_treated_as_epoch_zero_and_revoked(db):
    """구버전 쿠키(iat 없음)는 폐기 기준이 있으면 무효화된다."""
    user = _user(db)
    revoke_user_sessions(db, user)
    assert is_session_revoked(db, user.id, iat=0) is True


def test_revoke_by_email_raises_for_unknown_email(db):
    import pytest

    with pytest.raises(ValueError):
        revoke_sessions_by_email(db, "ghost@test.com")


def test_revoke_by_email_normalizes_case(db):
    user = _user(db, email="case@test.com")
    revoke_sessions_by_email(db, "  CASE@TEST.COM  ")
    assert is_session_revoked(db, user.id, iat=int(time.time())) is True
