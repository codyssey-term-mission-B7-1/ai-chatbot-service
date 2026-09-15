"""필터 값 자동완성 — 관리자 전용·화이트리스트·인젝션 방어(#204)."""

import pytest

from app.services.admin import grant_admin
from tests.conftest import signup_and_login


@pytest.fixture()
def admin_client(client, db):
    signup_and_login(client, "sugg@example.com")
    grant_admin(db, "sugg@example.com")
    return client


def test_suggest_requires_admin(client):
    assert client.get("/api/admin/suggest", params={"field": "email"}).status_code == 401
    signup_and_login(client)
    assert client.get("/api/admin/suggest", params={"field": "email"}).status_code == 403


def test_suggest_unknown_field_400(admin_client):
    assert admin_client.get("/api/admin/suggest", params={"field": "password"}).status_code == 400


def test_suggest_emails_by_prefix(admin_client, db):
    from app.repositories.users import create_user

    for email in ("anna@example.com", "annb@example.com", "bob@example.com"):
        create_user(db, email=email, password_hash="x" * 60, nickname=email.split("@")[0])

    items = admin_client.get("/api/admin/suggest", params={"field": "email", "q": "ann"}).json()[
        "items"
    ]
    assert items == ["anna@example.com", "annb@example.com"]


def test_suggest_thread_event_table(admin_client):
    tid = admin_client.post("/api/thread").json()["id"]
    threads = admin_client.get(
        "/api/admin/suggest", params={"field": "thread", "q": str(tid)}
    ).json()
    assert threads["items"][0]["id"] == tid
    events = admin_client.get(
        "/api/admin/suggest", params={"field": "event", "q": "ai_call"}
    ).json()["items"]
    assert "ai_call_fail" in events and all(e.startswith("ai_call") for e in events)
    tables = admin_client.get("/api/admin/suggest", params={"field": "table", "q": "user"}).json()
    assert tables["items"] == ["users"]


def test_suggestion_result_count_capped(admin_client):
    body = admin_client.get("/api/admin/suggest", params={"field": "event", "q": ""}).json()
    assert len(body["items"]) <= 8


def test_email_partial_match_and_wildcards_are_literal(client, db, fake_ai):
    """email: 부분일치 검색 + %·_는 와일드카드가 아니라 문자 그대로(#204)."""
    from app.models import User

    # walker가 질문한 기록을 만든다(세션은 viewer 관리자)
    db.add(User(email="walker@example.com", password_hash="x" * 60, nickname="w"))
    db.commit()
    signup_and_login(client, "viewer@example.com")
    client.post("/api/chats", json={"question": "뷰어 질문"})
    grant_admin(db, "viewer@example.com")

    page = client.get("/admin/logs", params={"filter": "email:walker"})
    assert page.status_code == 200
    assert "뷰어 질문" not in page.text  # viewer 기록이 walker로 잘못 매칭되지 않는다
    page = client.get("/admin/logs", params={"filter": "email:viewer"})
    assert "뷰어 질문" in page.text  # 부분일치(접두사 아님) 동작

    # 와일드카드 문자 자체는 문자 그대로만 매칭된다 — %가 모든 이메일에 풀리지 않는다
    everything = client.get("/admin/logs", params={"filter": "email:%"}).text
    assert "뷰어 질문" not in everything  # %가 모든 이메일에 매칭했다면 viewer 기록도 보임


def test_suggest_values_never_leak_question_content(admin_client, fake_ai):
    admin_client.post("/api/chats", json={"question": "비밀 질문 원문"})
    for field in ("email", "thread", "event", "path", "table"):
        body = admin_client.get("/api/admin/suggest", params={"field": field, "q": "비밀"}).text
        assert "비밀 질문 원문" not in body, f"{field} 후보에 콘텐츠 원문이 노출되지 않아야 한다"


def test_db_table_filter_rejects_injection_names(client, db):
    signup_and_login(client, "inj@example.com")
    grant_admin(db, "inj@example.com")
    for malicious in ("users; DROP TABLE users", "users' OR '1'='1", "users--"):
        r = client.get("/api/admin/db/tables", params={"filter": f"table:{malicious}"})
        assert r.status_code == 200  # 필터는 무해(존재하지 않는 이름 → 매칭 없음)
        r2 = client.get("/api/admin/db/tables", params={"table": malicious})
        assert r2.status_code == 200
    assert client.get("/admin/db", params={"table": "users"}).status_code == 200
