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
    assert "8자 이상" in client.get("/signup").text        # mode == 'signup'
    assert "계정이 없나요?" in client.get("/login").text    # mode != 'signup'

    signup_and_login(client)
    fake_ai.error = httpx.TimeoutException("timeout")
    client.post("/api/chat", json={"question": "실패 질문"})

    assert "row-error" in client.get("/logs").text          # status == 'ai_error'
