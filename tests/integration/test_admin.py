"""명시적 앱 관리자 권한과 사용자 데이터 격리. 데모 이름/클라이언트 입력으로 승격 불가."""

import pytest

from app.models import AdminGrant, User
from app.services.admin import grant_admin, is_admin, revoke_admin
from tests.conftest import signup_and_login


def test_non_admin_cannot_access_admin_api_or_page(client):
    signup_and_login(client)
    assert client.get("/api/auth/me").json()["is_admin"] is False
    assert client.get("/api/admin/chats").status_code == 403
    assert client.get("/admin/logs").status_code == 403
    assert "관리자 조회" not in client.get("/").text


def test_admin_reads_all_users_but_ordinary_endpoint_stays_isolated(client, db):
    signup_and_login(client, "one@example.com")
    client.post("/api/chat", json={"question": "첫 사용자"})
    signup_and_login(client, "two@example.com")
    client.post("/api/chat", json={"question": "다른 사용자"})
    user = grant_admin(db, "two@example.com")
    assert client.get("/api/auth/me").json()["is_admin"] is True
    response = client.get("/api/admin/chats")
    assert response.status_code == 200
    assert {r["question"] for r in response.json()["items"]} == {"첫 사용자", "다른 사용자"}
    assert {r["question"] for r in client.get("/api/me/chats").json()} == {"다른 사용자"}
    filtered = client.get("/api/admin/chats", params={"user_id": user.id}).json()["items"]
    assert len(filtered) == 1 and filtered[0]["user_id"] == user.id
    assert client.get("/admin/logs").status_code == 200
    assert "관리자 조회" in client.get("/").text


def test_admin_revoke_takes_effect_without_waiting_for_cookie_expiry(client, db):
    signup_and_login(client, "operator@example.com")
    grant_admin(db, "operator@example.com")
    assert client.get("/api/admin/chats").status_code == 200
    assert revoke_admin(db, "operator@example.com")
    assert client.get("/api/admin/chats").status_code == 403


def test_demo_accounts_cannot_be_promoted(client, db):
    signup_and_login(client, "admin@demo.com")
    with pytest.raises(ValueError, match="데모 계정"):
        grant_admin(db, "admin@demo.com")
    assert client.get("/api/admin/chats").status_code == 403


def test_grant_requires_existing_user_and_binds_to_account_email(db):
    with pytest.raises(ValueError, match="먼저"):
        grant_admin(db, "absent@example.com")
    db.add(User(id=1, email="new@example.com", password_hash="test-only", nickname="new"))
    db.flush()
    db.add(AdminGrant(user_id=1, granted_email="old@example.com"))
    db.commit()
    assert not is_admin(db, db.get(User, 1))


def test_admin_pagination_does_not_repeat_rows(client, db):
    signup_and_login(client, "pagination@example.com")
    for i in range(3):
        client.post("/api/chat", json={"question": f"기록 {i}"})
    grant_admin(db, "pagination@example.com")
    first = client.get("/api/admin/chats?limit=2").json()
    second = client.get(
        "/api/admin/chats",
        params={
            "limit": 2,
            "before_id": first["next_before_id"],
        },
    ).json()
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    assert {r["id"] for r in first["items"]}.isdisjoint(r["id"] for r in second["items"])
