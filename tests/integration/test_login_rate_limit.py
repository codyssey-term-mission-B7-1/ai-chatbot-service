"""통합 테스트 — 로그인 무차별 대입 방어·타이밍 평탄화(#72)."""

import logging

from app.services.rate_limit import login_limiter
from tests.conftest import signup_and_login


def test_repeated_failures_lock_even_the_correct_password(client, caplog):
    login_limiter.max_events = 3
    signup_and_login(client, email="lock@example.com", password="Password123!")

    for _ in range(3):
        response = client.post(
            "/api/auth/login", json={"email": "lock@example.com", "password": "wrong-pass"}
        )
        assert response.status_code == 401

    # 잠금 중에는 올바른 비밀번호도 거부 — 공격자가 성공 비밀번호를 찾아도 계속 못 들어온다.
    blocked = client.post(
        "/api/auth/login", json={"email": "lock@example.com", "password": "Password123!"}
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert "잠시 후" in blocked.json()["detail"]
    assert any("event=user_login_locked" in r.message for r in caplog.records)


def test_successful_login_resets_failure_counter(client):
    login_limiter.max_events = 2
    signup_and_login(client, email="reset@example.com", password="Password123!")

    client.post("/api/auth/login", json={"email": "reset@example.com", "password": "nope1234"})
    ok = client.post(
        "/api/auth/login", json={"email": "reset@example.com", "password": "Password123!"}
    )
    assert ok.status_code == 200
    # 성공으로 카운터가 초기화됐으므로 이후 실패 1건으로는 잠기지 않는다.
    again = client.post(
        "/api/auth/login", json={"email": "reset@example.com", "password": "nope1234"}
    )
    assert again.status_code == 401


def test_unknown_email_failures_also_lock(client):
    login_limiter.max_events = 2
    for _ in range(2):
        response = client.post(
            "/api/auth/login", json={"email": "ghost@example.com", "password": "whatever1"}
        )
        assert response.status_code == 401
    blocked = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "whatever1"}
    )
    assert blocked.status_code == 429


def test_dummy_verification_runs_only_for_unknown_email(client, monkeypatch):
    """존재하지 않는 이메일에만 더미 bcrypt가 수행되는지 호출 여부로 검증한다."""
    calls: list[str] = []

    def spy(password: str) -> None:
        calls.append(password)

    monkeypatch.setattr("app.routers.auth.verify_dummy_password", spy)
    signup_and_login(client, email="known@example.com", password="Password123!")

    unknown = client.post(
        "/api/auth/login", json={"email": "ghost2@example.com", "password": "typed-guess"}
    )
    assert unknown.status_code == 401
    assert calls == ["typed-guess"]

    # 가입된 이메일 경로는 더미 검증을 거치지 않는다.
    known = client.post(
        "/api/auth/login", json={"email": "known@example.com", "password": "wrong-pass"}
    )
    assert known.status_code == 401
    assert calls == ["typed-guess"]


def test_login_fail_event_does_not_log_email_plaintext(client, caplog):
    signup_and_login(client, email="secret-user@example.com", password="Password123!")
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        response = client.post(
            "/api/auth/login", json={"email": "secret-user@example.com", "password": "wrong-pass"}
        )
    assert response.status_code == 401
    fail_logs = [r.message for r in caplog.records if "event=user_login_fail" in r.message]
    assert fail_logs, caplog.text
    assert "secret-user@example.com" not in fail_logs[0]
    assert "email_domain=example.com" in fail_logs[0]


def test_lockout_applies_per_email(client):
    login_limiter.max_events = 1
    signup_and_login(client, email="first@example.com", password="Password123!")
    signup_and_login(client, email="second@example.com", password="Password123!")

    client.post("/api/auth/login", json={"email": "first@example.com", "password": "bad-pass1"})
    blocked = client.post(
        "/api/auth/login", json={"email": "first@example.com", "password": "Password123!"}
    )
    assert blocked.status_code == 429
    # 다른 이메일은 영향을 받지 않는다.
    other = client.post(
        "/api/auth/login", json={"email": "second@example.com", "password": "Password123!"}
    )
    assert other.status_code == 200
