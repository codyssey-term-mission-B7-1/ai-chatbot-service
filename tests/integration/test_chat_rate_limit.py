"""통합 테스트 — 채팅 사용자별 rate limit·AI 호출 전 커넥션 반납(#73)."""

import logging

from app.services.rate_limit import chat_limiter
from tests.conftest import signup_and_login


def test_exceeding_per_minute_cap_returns_429(client, monkeypatch, caplog):
    monkeypatch.setattr(chat_limiter, "max_events", 2)
    signup_and_login(client, email="rate@example.com")

    assert client.post("/api/chat", json={"question": "첫째"}).status_code == 200
    assert client.post("/api/chat", json={"question": "둘째"}).status_code == 200

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        blocked = client.post("/api/chat", json={"question": "셋째"})
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert "RATE_LIMITED" in blocked.json()["detail"]
    assert any("event=chat_rate_limited" in r.message for r in caplog.records)
    # 제한된 요청은 AI 호출·DB 저장로 진행되지 않는다.
    assert not any("event=ai_call_start" in r.message for r in caplog.records)
    assert not any("event=db_save_success" in r.message for r in caplog.records)
    assert len(client.get("/api/me/chats").json()) == 2


def test_zero_disables_chat_rate_limit(client, monkeypatch):
    monkeypatch.setattr(chat_limiter, "max_events", 0)
    signup_and_login(client, email="free@example.com")
    for i in range(12):
        response = client.post("/api/chat", json={"question": f"질문 {i}"})
        assert response.status_code == 200


def test_rate_limit_applies_per_user(client, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(chat_limiter, "max_events", 1)
    signup_and_login(client, email="first-user@example.com")
    with TestClient(app) as other:
        signup_and_login(other, email="second-user@example.com")
        assert other.post("/api/chat", json={"question": "하나"}).status_code == 200
        assert other.post("/api/chat", json={"question": "둘"}).status_code == 429
    # 다른 사용자의 한도는 독립적이다.
    assert client.post("/api/chat", json={"question": "별개"}).status_code == 200


def test_context_restoration_still_matches_ai_after_commit_release(client, fake_ai):
    """커넥션 반납(commit) 이후에도 문맥 구성·저장 파이프라인이 그대로 동작한다."""
    signup_and_login(client, email="pipeline@example.com")
    assert client.post("/api/chat", json={"question": "배포 방법"}).status_code == 200
    assert client.post("/api/chat", json={"question": "방금 뭐라고 했지?"}).status_code == 200

    sent = [m["content"] for m in fake_ai.last_messages if m["role"] == "user"]
    assert sent[-1] == "방금 뭐라고 했지?"
    assert "배포 방법" in sent  # 직전 성공 Q/A가 문맥으로 전달됐다
    logs = client.get("/api/me/chats?status=success").json()
    assert len(logs) == 2
