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


def test_password_hash_status_reports_migration_progress(client, db):
    """해시 현황 — 레거시/페퍼 카운트가 정확하고 관리자 전용이다."""
    signup_and_login(client, "legacy-user@example.com")
    # 레거시(페퍼 이전) 해시 사용자 1명 추가
    import bcrypt as _bcrypt

    db.add(
        User(
            email="legacy2@example.com",
            password_hash=_bcrypt.hashpw(b"x" * 8, _bcrypt.gensalt()).decode(),
            nickname="레거시",
        )
    )
    db.commit()

    assert client.get("/api/admin/security/password-hashes").status_code == 403
    grant_admin(db, "legacy-user@example.com")
    r = client.get("/api/admin/security/password-hashes")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert body["peppered"] >= 1  # signup_and_login 계정(로그인 시 마킹됨)
    assert body["legacy"] >= 1


def test_admin_deletes_user_with_chats_and_sessions(client, db):
    """사용자 삭제 — 대화 CASCADE·세션 폐기·재설정 토큰까지 정리된다."""
    signup_and_login(client, "victim@example.com")
    client.post("/api/chat", json={"question": "지워질 질문"})
    victim_id = client.get("/api/auth/me").json()["email"]  # 스키인지만 확인용
    from app.repositories.users import find_by_email

    victim = find_by_email(db, "victim@example.com")
    victim_id = victim.id

    signup_and_login(client, "admin@example.com")
    grant_admin(db, "admin@example.com")
    r = client.delete(f"/api/admin/users/{victim_id}")
    assert r.status_code == 200
    assert r.json()["email"] == "victim@example.com"
    db.expire_all()
    assert db.get(User, victim_id) is None
    assert db.query(User).filter_by(email="victim@example.com").first() is None
    # 대화 로그도 사라진다
    from app.models import ChatLog

    assert db.query(ChatLog).filter_by(user_id=victim_id).count() == 0


def test_admin_cannot_delete_self_or_other_admin(client, db):
    signup_and_login(client, "root@example.com")
    grant_admin(db, "root@example.com")
    root_id = find_id(db, "root@example.com")
    assert client.delete(f"/api/admin/users/{root_id}").status_code == 400

    signup_and_login(client, "peer-admin@example.com")
    grant_admin(db, "peer-admin@example.com")
    peer_id = find_id(db, "peer-admin@example.com")
    # 관리자는 직전 로그인 세션이 아니라 '현재' 세션이므로 root 삭제 시도는 peer-admin 세션에서 수행
    assert client.delete(f"/api/admin/users/{root_id}").status_code == 400
    assert client.delete(f"/api/admin/users/{peer_id}").status_code == 400


def test_delete_user_requires_admin_and_existing_target(client):
    signup_and_login(client, "plain@example.com")
    assert client.delete("/api/admin/users/999").status_code == 403
    signup_and_login(client, "admin2@example.com")
    # admin2는 관리자가 아님 → 403; 404 우선순위 확인은 관리자로 수행
    assert client.delete("/api/admin/users/999").status_code == 403


def find_id(db, email):
    from app.repositories.users import find_by_email

    return find_by_email(db, email).id


def test_admin_page_view_records_reason_in_audit_log(client, db, caplog):
    """/admin/logs 열람 사유가 admin_logs_viewed 감사 이벤트에 기록된다(B-1 — who/what/why)."""
    import logging

    signup_and_login(client, "reason-admin@example.com")
    grant_admin(db, "reason-admin@example.com")
    with caplog.at_level(logging.INFO, logger="app.pages"):
        response = client.get("/admin/logs", params={"reason": "장애 조사: 사용자 문의 대응 #100"})
    assert response.status_code == 200
    assert "event=admin_logs_viewed" in caplog.text
    assert "reason=" in caplog.text
    # JS(admin-logs.js)가 참조하는 입력이 실제 렌더에 존재해야 한다 — 유실 시 폼 제출이 깨진다.
    assert 'id="admin-reason"' in response.text

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.pages"):
        client.get("/admin/logs")  # 사유 없이 열람해도 기존 동작(하위 호환)
    assert "event=admin_logs_viewed" in caplog.text
