"""저장 실패는 AI 성공과 분리하고 원문/SQL 파라미터를 로그에 노출하지 않는다."""

import logging

from app.repositories import chat_logs
from tests.conftest import signup_and_login


def test_db_failure_does_not_claim_persisted_chat_or_log_sensitive_text(
    client, monkeypatch, caplog
):
    signup_and_login(client)

    def fail(*args, **kwargs):
        raise RuntimeError("private query arguments must not enter logs")

    monkeypatch.setattr(chat_logs, "save_log", fail)
    with caplog.at_level(logging.INFO):
        response = client.post("/api/chat", json={"question": "private user question"})
    assert response.status_code == 200
    assert response.json()["status"] == "success" and response.json()["chat_id"] == -1
    assert "private user question" not in caplog.text
    assert "private query arguments" not in caplog.text
    assert any("event=db_save_fail" in r.message for r in caplog.records)
