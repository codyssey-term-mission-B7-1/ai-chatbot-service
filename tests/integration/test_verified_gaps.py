"""D01~D10/D12/D19 회귀. 실제 운영/외부 AI 요청이 아닌 격리 DB 테스트."""

import logging
from datetime import datetime, timezone

import httpx
import pytest
from starlette.middleware.sessions import SessionMiddleware

from app.logging_config import REQUEST_ID
from app.models import ChatLog
from app.policies import SECURITY_HEADERS
from app.services.ai_client import OpenAICompatClient, get_ai_provider
from tests.conftest import signup_and_login


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("가" * 24, 201),
        ("가" * 25, 422),
        ("a" * 64, 201),
    ],
)
def test_password_byte_boundary_is_a_validation_error(client, value, expected):
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "bytes@example.com",
            "password": value,
        },
    )
    assert response.status_code == expected
    if expected == 422:
        assert "72바이트" in response.text
        assert all("input" not in x for x in response.json()["detail"])


def test_generated_nickname_respects_maximum(client):
    email = "n" * 25 + "@example.com"
    response = client.post("/api/auth/signup", json={"email": email, "password": "Password123!"})
    assert response.status_code == 201 and len(response.json()["nickname"]) == 20


def test_signup_does_not_accept_client_admin_flag(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "escalation@example.com",
            "password": "Password123!",
            "is_admin": True,
        },
    )
    assert response.status_code == 422


def test_html_redirects_and_api_auth_errors_are_separate(client):
    for path in ["/logs", "/admin/logs"]:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302 and response.headers["location"] == "/login"
    assert client.get("/api/me/chats").status_code == 401
    assert client.get("/api/admin/chats").status_code == 401


def test_session_is_outermost_and_log_identity_is_explicit(client, caplog):
    from app.main import app

    assert app.user_middleware[0].cls is SessionMiddleware
    signup_and_login(client)
    caplog.clear()
    with caplog.at_level(logging.INFO):
        response = client.get("/api/auth/me")
    received = [r.message for r in caplog.records if "event=request_received" in r.message]
    finished = [r.message for r in caplog.records if "event=request_finished" in r.message]
    assert len(received) == len(finished) == 1
    assert "session_user_id=1" in received[0] and "user_id=1" in finished[0]
    assert response.headers["x-request-id"] in received[0]
    assert REQUEST_ID.get() is None  # context does not leak into another request


def test_one_http_received_event_and_no_question_logging(client, caplog):
    signup_and_login(client)
    secret_question = "민감한 질문 첫째 줄\n둘째 줄"
    caplog.clear()
    with caplog.at_level(logging.INFO):
        response = client.post("/api/chat", json={"question": secret_question})
    assert response.status_code == 200
    events = [r.message for r in caplog.records if "event=" in r.message]
    assert sum("event=request_received " in m for m in events) == 1
    assert all(secret_question not in m and "첫째 줄" not in m for m in events)
    request_id = response.headers["x-request-id"]
    for event in ["ai_call_start", "ai_call_success", "db_save_success", "request_finished"]:
        assert any("event=" + event + " " in m and request_id in m for m in events)


def test_unhandled_500_has_security_headers_and_finished_log(client, monkeypatch, caplog):
    from app.routers import auth

    def unexpected(*args, **kwargs):
        raise RuntimeError("sensitive exception detail should not enter logs")

    monkeypatch.setattr(auth, "create_user", unexpected)
    client._transport.raise_server_exceptions = False
    caplog.clear()
    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/auth/signup",
            json={
                "email": "failure@example.com",
                "password": "Password123!",
            },
        )
    assert response.status_code == 500 and "INTERNAL" in response.json()["detail"]
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value
    assert response.headers["x-request-id"]
    assert any(
        "event=request_finished" in r.message and "status=500" in r.message for r in caplog.records
    )
    assert "sensitive exception detail" not in caplog.text
    assert client.get("/health").status_code == 200


def test_success_filter_precedes_limit_and_matches_ai_context(client, db, fake_ai):
    signup_and_login(client)
    for i in range(5):
        db.add(ChatLog(user_id=1, question=f"success-{i}", answer="ok", status="success"))
    for i in range(50):
        db.add(ChatLog(user_id=1, question=f"error-{i}", answer="", status="ai_error"))
    db.commit()
    restored = client.get("/api/me/chats?status=success&limit=5").json()
    assert len(restored) == 5
    client.post("/api/chat", json={"question": "다음 질문"})
    sent = [m["content"] for m in fake_ai.last_messages[1:-1] if m["role"] == "user"]
    assert sent == [r["question"] for r in reversed(restored)]
    assert client.get("/api/me/chats?status=unknown").status_code == 422


def test_zero_context_disables_history(client, monkeypatch, fake_ai):
    from app.config import settings

    signup_and_login(client)
    client.post("/api/chat", json={"question": "첫 질문"})
    monkeypatch.setattr(settings, "context_turns", 0)
    client.post("/api/chat", json={"question": "두 번째 질문"})
    assert len(fake_ai.last_messages) == 2


def test_utc_marker_survives_sqlite_roundtrip(client, db):
    signup_and_login(client)
    db.add(
        ChatLog(
            user_id=1,
            question="UTC",
            answer="ok",
            status="success",
            created_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
        )
    )
    db.commit()
    record = client.get("/api/me/chats?limit=1").json()[0]
    assert record["created_at"] == "2026-09-08T00:00:00Z"
    assert "시각 (UTC)" in client.get("/logs").text


def test_malformed_multipart_maps_to_502_and_is_saved(client, monkeypatch):
    from app.main import app

    signup_and_login(client)

    async def malformed(self, *args, **kwargs):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": None},
                            ]
                        }
                    }
                ]
            },
            request=httpx.Request("POST", "https://example.test/v1/chat/completions"),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", malformed)
    provider = OpenAICompatClient("not-real", "https://example.test/v1", "test", 2, 0)
    app.dependency_overrides[get_ai_provider] = lambda: provider
    response = client.post("/api/chat", json={"question": "합성 응답 오류"})
    assert response.status_code == 502 and "AI_ERROR" in response.json()["detail"]
    assert client.get("/api/me/chats?limit=1").json()[0]["status"] == "ai_error"


def test_swagger_links_are_absolute_and_descriptions_match_contract(client):
    schema = client.get("/openapi.json").json()
    description = schema["info"]["description"]
    assert "DB 저장 시도" in description and "chat_id=-1" in description
    assert "(../" not in description
    assert "https://github.com/codyssey-term-mission-B7-1/ai-chatbot-service/" in description
    for path, methods in schema["paths"].items():
        for operation in methods.values():
            assert operation.get("summary"), path
            assert operation.get("description"), path
    assert "/api/admin/chats" in schema["paths"]


def test_invalid_unicode_question_returns_422_without_echoing_input(client):
    signup_and_login(client)
    response = client.post(
        "/api/chat", content=b'{"question":"\\ud800"}', headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert all("input" not in x for x in response.json()["detail"])


def test_router_budget_also_bounds_an_injected_slow_provider(client, fake_ai, monkeypatch):
    import asyncio

    from app.config import settings

    signup_and_login(client)

    async def slow(messages):
        await asyncio.sleep(0.2)
        return "late"

    monkeypatch.setattr(fake_ai, "generate", slow)
    monkeypatch.setattr(settings, "ai_timeout_sec", 0.01)
    assert client.post("/api/chat", json={"question": "느린 제공자"}).status_code == 504
    assert client.get("/health").status_code == 200
