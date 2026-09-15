"""관리자 콘솔 — 대시보드·이벤트 로그·네트워크 로그·DB 브라우저(#189)."""


from app.services.admin import grant_admin
from tests.conftest import signup_and_login

CONSOLE_APIS = (
    "/api/admin/stats",
    "/api/admin/events",
    "/api/admin/network",
    "/api/admin/db/tables",
)
CONSOLE_PAGES = ("/admin", "/admin/events", "/admin/network", "/admin/db", "/admin/logs")


def test_console_requires_login_or_admin(client):
    api_codes = {api: client.get(api).status_code for api in CONSOLE_APIS}
    page_codes = {
        page: client.get(page, follow_redirects=False).status_code for page in CONSOLE_PAGES
    }
    assert all(c == 401 for c in api_codes.values()), api_codes
    assert all(c == 302 for c in page_codes.values()), page_codes

    signup_and_login(client)
    api_codes = {api: client.get(api).status_code for api in CONSOLE_APIS}
    page_codes = {
        page: client.get(page, follow_redirects=False).status_code for page in CONSOLE_PAGES
    }
    assert all(c == 403 for c in api_codes.values()), api_codes
    assert all(c == 403 for c in page_codes.values()), page_codes


def test_dashboard_stats_and_persisted_logs(client, db, fake_ai):
    signup_and_login(client, "console@example.com")
    client.post("/api/chats", json={"question": "콘솔 질문"})

    grant_admin(db, "console@example.com")

    stats = client.get("/api/admin/stats").json()
    assert stats["users"] >= 1 and stats["chats"] >= 1 and stats["chats_success"] >= 1

    # 이벤트 로그 — 채팅 파이프라인 이벤트가 DB에 남는다
    events = client.get("/api/admin/events").json()["items"]
    names = {e["event"] for e in events}
    assert {"ai_call_start", "ai_call_success", "request_finished"} <= names
    mine = [e for e in events if e["event"] == "ai_call_start"]
    assert mine and mine[0]["user_id"]

    # 네트워크 로그 — /api/ 요청이 기록된다
    rows = client.get("/api/admin/network").json()["items"]
    assert any(r["path"] == "/api/chats" and r["status"] == 201 for r in rows)
    assert any(r["path"] == "/api/session" for r in rows)

    # 이벤트 이름 필터
    filtered = client.get("/api/admin/events", params={"event": "ai_call_start"}).json()["items"]
    assert filtered and all(e["event"] == "ai_call_start" for e in filtered)


def test_console_pages_render(client, db):
    signup_and_login(client, "pager@example.com")
    client.post("/api/chats", json={"question": "페이지 질문"})
    grant_admin(db, "pager@example.com")

    dash = client.get("/admin")
    assert dash.status_code == 200 and "대시보드" in dash.text and "관리자 메뉴" in dash.text
    events = client.get("/admin/events")
    assert events.status_code == 200 and "ai_call_start" in events.text
    network = client.get("/admin/network")
    assert network.status_code == 200 and "/api/chats" in network.text
    db_page = client.get("/admin/db")
    assert db_page.status_code == 200 and "users" in db_page.text
    rows = client.get("/admin/db", params={"table": "users"})
    assert rows.status_code == 200 and "pager@example.com" in rows.text


def test_db_browser_whitelist_and_readonly(client, db):
    signup_and_login(client, "dba@example.com")
    grant_admin(db, "dba@example.com")
    # 앱 소유 테이블만 화이트리스트 — 인프라 테이블(alembic_version)·미지 이름은 404
    assert client.get("/api/admin/db/tables/alembic_version/rows").status_code == 404
    assert client.get("/api/admin/db/tables/no_such_table/rows").status_code == 404
    # SQL 주입 시도도 화이트리스트 밖이면 404
    assert (
        client.get("/api/admin/db/tables/users%3B%20DROP%20TABLE%20users/rows").status_code == 404
    )


def test_recorder_failure_never_breaks_requests(client, db, monkeypatch, fake_ai):
    """best-effort 보장 — DB 기록기가 죽어도 본 요청은 정상 처리된다."""
    signup_and_login(client, "resilient@example.com")

    from app import database

    def broken_session():
        raise RuntimeError("DB 기록기 장애")

    monkeypatch.setattr(database, "SessionLocal", broken_session)
    r = client.post("/api/chats", json={"question": "장애 중 질문"})
    assert r.status_code == 201
