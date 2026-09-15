"""통합 테스트 — HTML 페이지 렌더링.

기존 테스트가 JSON API만 검증해 템플릿 경로/문법 오류(500)를 놓쳤던 회귀를 방지한다.
"""

import httpx

from tests.conftest import signup_and_login


def test_all_pages_render(client):
    """네 개 HTML 페이지가 템플릿을 찾아 정상 렌더된다 (템플릿 경로 회귀 방지)."""
    for path in ("/login", "/signup"):
        assert client.get(path).status_code == 200, path

    signup_and_login(client)
    for path in ("/", "/logs"):
        assert client.get(path).status_code == 200, path


def test_templates_render_conditional_branches(client, fake_ai):
    """템플릿의 조건 분기가 평가된다 (Jinja2 삼항 문법 회귀 방지)."""
    assert "8자 이상" in client.get("/signup").text  # mode == 'signup'
    assert "계정이 없나요?" in client.get("/login").text  # mode != 'signup'

    signup_and_login(client)
    fake_ai.error = httpx.TimeoutException("timeout")
    client.post("/api/chats", json={"question": "실패 질문"})

    assert "row-error" in client.get("/logs").text  # status == 'ai_error'


def test_empty_ai_api_key_is_reported_as_demo_mode(client, monkeypatch):
    """`AI_API_KEY=`(빈 문자열)는 .env.example 기본값 — Fake 응답인데 '실연결'로 보이면 안 된다."""
    from app.config import settings
    from tests.conftest import signup_and_login

    monkeypatch.setattr(settings, "ai_api_key", "")
    assert client.get("/health").json()["ai_mode"] == "demo"
    signup_and_login(client)
    assert "데모 모드" in client.get("/").text


def test_logs_redirects_to_login_when_logged_out(client):
    """비로그인 /logs → 302 /login (접근 제어 매트릭스 일치, #10)."""
    res = client.get("/logs", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/login"


def test_logs_shows_my_logs_when_logged_in(client, fake_ai):
    """로그인 /logs → 200 + 빈 상태 문구, 채팅 후 내 기록 테이블 렌더."""
    signup_and_login(client)
    assert "아직 대화 기록이 없어요" in client.get("/logs").text  # 빈 상태
    client.post("/api/chats", json={"question": "첫 질문"})
    res = client.get("/logs")
    assert res.status_code == 200
    assert "logs-table" in res.text
    assert "첫 질문" in res.text


def test_signup_page_discloses_admin_review_login_does_not(client):
    """가입 화면에만 관리자 열람 고지가 노출된다(B-1 — 데이터 정책 초안과 함께 고지 계약)."""
    signup = client.get("/signup").text
    login = client.get("/login").text
    assert "관리자가 대화 내용을 열람할 수 있어요" in signup
    assert "감사 로그로 남습니다" in signup
    assert "관리자가 대화 내용을 열람" not in login  # 로그인 화면은 고지 아님


def test_chat_textarea_html_guards(client):
    """HTML 계층 방어 — 빈 입력(required)·길이 상한(maxlength)이 폼 속성으로 존재해야 한다(#192)."""
    import re

    signup_and_login(client)
    page = client.get("/").text
    match = re.search(r'<textarea id="question"[^>]*>', page)
    assert match, "질문 textarea가 렌더되어야 한다"
    tag = match.group(0)
    assert "required" in tag, "빈 입력 HTML 차단(required)이 있어야 한다"
    max_len = re.search(r'maxlength="(\d+)"', tag)
    assert max_len and int(max_len.group(1)) >= 1000, "길이 상한 maxlength가 있어야 한다"
