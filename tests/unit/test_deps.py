"""유닛 테스트 — 세션→사용자 해석 + 계정 바인딩 검증 (#33)."""
from types import SimpleNamespace

from app.deps import resolve_session_user
from app.models import User
from app.services.security import email_fingerprint, hash_password


def _request(session: dict):
    return SimpleNamespace(session=dict(session))


def _user(db, email="a@test.com", nickname="에이"):
    user = User(email=email, password_hash=hash_password("pw"), nickname=nickname)
    db.add(user)
    db.commit()
    return user


def test_resolve_session_user_returns_user_on_match(db):
    user = _user(db)
    req = _request({"user_id": user.id, "email_fp": email_fingerprint(user.email)})
    assert resolve_session_user(req, db).id == user.id


def test_resolve_session_user_none_without_session(db):
    assert resolve_session_user(_request({}), db) is None


def test_resolve_session_user_clears_unknown_id(db):
    req = _request({"user_id": 9999, "email_fp": "deadbeefdeadbeef"})
    assert resolve_session_user(req, db) is None
    assert req.session == {}  # 세션 파기됨


def test_resolve_session_user_clears_email_mismatch(db):
    user = _user(db)  # stale 쿠키: 같은 id, 다른 이메일 (DB 재생성 시나리오)
    req = _request({"user_id": user.id, "email_fp": email_fingerprint("old@test.com")})
    assert resolve_session_user(req, db) is None
    assert req.session == {}


def test_resolve_session_user_clears_garbage_id(db):
    req = _request({"user_id": "not-an-int", "email_fp": email_fingerprint("a@test.com")})
    assert resolve_session_user(req, db) is None
    assert req.session == {}


def test_fingerprint_is_not_the_plaintext_email():
    """바인딩 값이 이메일 그 자체면 개인정보가 쿠키로 나간다 (#59)."""
    fp = email_fingerprint("alice@example.com")
    assert "alice" not in fp and "@" not in fp and len(fp) == 16
    assert fp == email_fingerprint("alice@example.com")  # 결정적이어야 바인딩이 성립
