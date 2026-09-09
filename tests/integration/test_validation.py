"""통합 테스트 — /api/chat 입력 검증 경계값 (신규 파일, #11)."""

from tests.conftest import signup_and_login


def test_blank_question_rejected(client):
    signup_and_login(client)
    r = client.post("/api/chat", json={"question": "   "})
    assert r.status_code == 422


def test_missing_question_rejected(client):
    signup_and_login(client)
    r = client.post("/api/chat", json={})
    assert r.status_code == 422


def test_overlong_question_rejected(client):
    """1001자 → 422 (MAX_QUESTION_LENGTH=1000 경계)."""
    signup_and_login(client)
    r = client.post("/api/chat", json={"question": "가" * 1001})
    assert r.status_code == 422


def test_max_length_question_accepted(client, fake_ai):
    """정확히 1000자 → 검증 통과 (200)."""
    signup_and_login(client)
    r = client.post("/api/chat", json={"question": "가" * 1000})
    assert r.status_code == 200
