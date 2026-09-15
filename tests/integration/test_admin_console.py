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


def test_admin_logs_filter_is_native_form(client, db, fake_ai):
    """필터가 name 속성 기반 네이티브 GET으로 동작 — JS 없이 엔터 제출로 검색된다(#195)."""
    import re

    signup_and_login(client, "native@example.com")
    tid = client.post("/api/thread").json()["id"]
    client.post("/api/chats", json={"question": "네이티브 필터 질문", "thread_id": tid})
    grant_admin(db, "native@example.com")

    page = client.get("/admin/logs").text
    email_input = re.search(r'<input id="admin-user-email"[^>]*>', page).group(0)
    thread_select = re.search(r'<select id="admin-thread"[^>]*>', page).group(0)
    assert 'name="email"' in email_input, "이메일 필터가 네이티브 제출 가능해야 한다"
    assert 'name="thread"' in thread_select, "스레드 필터가 네이티브 제출 가능해야 한다"
    assert 'admin-logs.js' not in page, "JS 리다이렉트 없이 폼이 스스로 제출해야 한다"


def test_admin_logs_pagination_with_full_page(client, db, fake_ai):
    """50건이 채워지면 더 보기 링크가 생기고, before_id로 이전(오래된) 페이지를 본다(#195)."""
    signup_and_login(client, "paging@example.com")
    for i in range(55):
        r = client.post("/api/chats", json={"question": f"페이지네이션{i:02d}"})
        assert r.status_code == 201, i
    grant_admin(db, "paging@example.com")

    first = client.get("/admin/logs")
    assert first.text.count("페이지네이션") == 50
    assert "이전 기록 더 보기" in first.text

    cursor = 1  # 첫 페이지의 마지막(가장 오래된) 행 id — desc라 마지막이 최소 id
    rows = client.get("/api/admin/chats", params={"limit": 50}).json()["items"]
    cursor = rows[-1]["id"]
    second = client.get("/admin/logs", params={"before_id": cursor})
    assert second.status_code == 200
    assert second.text.count("페이지네이션") == 5
    assert "이전 기록이 더 없습니다" in second.text  # 소진 안내


def test_ai_call_fail_is_persisted_and_visible(client, db, fake_ai):
    """AI 실패 시 ai_call_fail이 DB에 남고 콘솔에서 필터해 볼 수 있다(#195)."""
    from app.services.ai_client import AIError

    signup_and_login(client, "fail@example.com")
    fake_ai.error = AIError("외부 AI 장애")
    r = client.post("/api/chats", json={"question": "실패할 질문"})
    assert r.status_code == 502
    fake_ai.error = None
    grant_admin(db, "fail@example.com")

    events_page = client.get("/admin/events").text
    assert 'value="ai_call_fail"' in events_page, "드롭다운에 카탈로그 전체가 있어야 한다"

    page = client.get("/admin/events", params={"event": "ai_call_fail"})
    assert page.status_code == 200 and "ai_call_fail" in page.text
    assert "실패할 질문" not in page.text  # 원문은 저장하지 않는다

    api_items = client.get("/api/admin/events", params={"event": "ai_call_fail"}).json()["items"]
    assert api_items and all(e["event"] == "ai_call_fail" for e in api_items)


def test_network_status_dropdown_covers_whole_table(client, db, fake_ai):
    """상태 드롭다운이 현재 페이지가 아니라 테이블 전체 DISTINCT를 담는다(#195)."""
    import re

    signup_and_login(client, "net@example.com")
    client.post("/api/chats", json={"question": "상태 드롭다운 질문"})
    grant_admin(db, "net@example.com")

    # 50건을 채우지 않아도(현재 페이지에 없는 상태라도) 전체 테이블의 상태가 옵션에 있다
    page = client.get("/admin/network").text
    select = re.search(r'<select name="status".*?</select>', page, re.S).group(0)
    assert 'value="201"' in select
