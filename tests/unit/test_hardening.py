"""P0-P2 하드닝 단위 테스트 — 비밀번호 블랙리스트, Retry-After 포매터, /readyz."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.password_policy import is_common_password
from app.services.rate_limit import retry_after_hint


@pytest.mark.parametrize(
    "pwd",
    [
        "password123",
        "PASSWORD123",
        "Password123!",
        "qwerty",
        "admin123",
        "123456",
        "11111111",
        "abc123",
        "password",
    ],
)
def test_common_passwords_are_flagged(pwd):
    assert is_common_password(pwd) is True


@pytest.mark.parametrize(
    "pwd",
    [
        "StrongP4ss!",
        "MyC0mpl!xPwd",
        "가나다라마바사아",
        "aB3!xQz9#mK",
    ],
)
def test_uncommon_passwords_pass(pwd):
    assert is_common_password(pwd) is False


@pytest.mark.parametrize(
    ("sec", "expected"),
    [
        (0, "약 0초 후"),
        (5, "약 5초 후"),
        (59, "약 59초 후"),
        (60, "약 1분 0초 후"),
        (65, "약 1분 5초 후"),
        (899, "약 14분 59초 후"),
    ],
)
def test_retry_after_hint(sec, expected):
    assert retry_after_hint(sec) == expected


def test_readyz_reports_ready_in_memory_db():
    with TestClient(app) as c:
        r = c.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert "version" in body


def test_health_and_readyz_are_unauthenticated():
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/readyz").status_code == 200
