"""통합 테스트 — 세션 수명 단축·서버 측 폐기(#74)."""

import base64
import json
import logging

from app.services.sessions import revoke_user_sessions
from tests.conftest import signup_and_login


def test_session_cookie_max_age_follows_setting(client, monkeypatch):
    """쿠키 수명이 SESSION_MAX_AGE_HOURS(기본 24시간=86400초)를 따른다."""
    from app.config import settings

    monkeypatch.setattr(settings, "session_max_age_hours", 24)
    signup_and_login(client, email="expiry@example.com")
    response = client.post(
        "/api/auth/login",
        json={"email": "expiry@example.com", "password": "Test1234!"},
    )
    cookie = response.headers.get_list("set-cookie")[0]
    assert "Max-Age=86400" in cookie, cookie


def test_revoked_session_is_rejected_until_relogin(client, db, caplog):
    signup_and_login(client, email="victim@example.com", password="Test1234!")
    assert client.get("/api/auth/me").status_code == 200

    from app.models import User

    user = db.query(User).filter(User.email == "victim@example.com").one()
    with caplog.at_level(logging.WARNING):
        revoke_user_sessions(db, user)

    # 기존 세션(쿠키)은 서명이 유효해도 거부된다.
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/chat", json={"question": "안녕"}).status_code == 401
    assert any("event=auth_session_revoked" in r.message for r in caplog.records)

    # 재로그인(폐기 이후 iat)은 정상 동작한다.
    assert (
        client.post(
            "/api/auth/login", json={"email": "victim@example.com", "password": "Test1234!"}
        ).status_code
        == 200
    )
    assert client.get("/api/auth/me").status_code == 200


def test_revocation_does_not_affect_other_accounts(client, db):
    signup_and_login(client, email="keep@example.com", password="Test1234!")

    from fastapi.testclient import TestClient

    from app.main import app
    from app.models import User

    with TestClient(app) as other:
        signup_and_login(other, email="kicked@example.com", password="Test1234!")
        assert other.get("/api/auth/me").status_code == 200
        kicked = db.query(User).filter(User.email == "kicked@example.com").one()
        revoke_user_sessions(db, kicked)
        assert other.get("/api/auth/me").status_code == 401

    # 다른 계정의 세션은 그대로 유지된다.
    assert client.get("/api/auth/me").status_code == 200


def test_login_stores_iat_in_cookie_payload(client):
    """쿠키 페이로드에 발급 시각(iat)이 정수로 들어간다 — 평문 이메일은 계속 없음."""
    signup_and_login(client, email="iat@example.com", password="Test1234!")
    response = client.post(
        "/api/auth/login", json={"email": "iat@example.com", "password": "Test1234!"}
    )
    signed = response.cookies.get("session")
    payload = json.loads(base64.b64decode(signed.split(".")[0] + "=="))
    assert isinstance(payload.get("iat"), int)
    assert "email" not in payload
