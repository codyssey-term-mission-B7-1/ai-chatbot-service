"""유닛 테스트 — 세션→사용자 해석 + 계정 바인딩 검증 (#33)."""
from types import SimpleNamespace

from app.deps import resolve_session_user
from app.models import User
from app.services.security import hash_password


def _request(session: dict):
    return SimpleNamespace(session=dict(session))


def _user(db, email="a@test.com", nickname="에이"):
    user = User(email=email, password_hash=hash_password("pw"), nickname=nickname)
    db.add(user)
    db.commit()
    return user


def test_resolve_session_user_returns_user_on_match(db):
    user = _user(db)
    req = _request({"user_id": user.id, "email": user.email})
    assert resolve_session_user(req, db).id == user.id


def test_resolve_session_user_none_without_session(db):
    assert resolve_session_user(_request({}), db) is None


def test_resolve_session_user_clears_unknown_id(db):
    req = _request({"user_id": 9999, "email": "ghost@test.com"})
    assert resolve_session_user(req, db) is None
    assert req.session == {}  # 세션 파기됨


def test_resolve_session_user_clears_email_mismatch(db):
    user = _user(db)  # stale 쿠키: 같은 id, 다른 이메일 (DB 재생성 시나리오)
    req = _request({"user_id": user.id, "email": "old@test.com"})
    assert resolve_session_user(req, db) is None
    assert req.session == {}


def test_resolve_session_user_clears_garbage_id(db):
    req = _request({"user_id": "not-an-int", "email": "a@test.com"})
    assert resolve_session_user(req, db) is None
    assert req.session == {}
