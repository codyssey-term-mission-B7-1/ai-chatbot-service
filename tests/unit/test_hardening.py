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


def test_health_schema_field_reflects_sync_state(monkeypatch):
    """/health.schema — 스키마 동기화 결과를 200 응답 안에서 노출(2026-09-13 사고 후).

    lifespan 없이(컨텍스트 미개봉) 호출해 전역 상태를 그대로 판정한다.
    """
    from app.database import schema_sync

    client = TestClient(app)
    monkeypatch.setitem(schema_sync, "status", "ok")
    monkeypatch.setitem(schema_sync, "error", None)
    assert client.get("/health").json()["schema"] == "ok"

    monkeypatch.setitem(schema_sync, "status", "error")
    monkeypatch.setitem(schema_sync, "error", "table_exists")
    assert client.get("/health").json()["schema"] == "error:table_exists"

    monkeypatch.setitem(schema_sync, "status", "pending")
    assert client.get("/health").json()["schema"] == "pending"


def test_readyz_503_when_schema_sync_failed(monkeypatch):
    """DB는 살아도 스키마 미반영이면 /readyz 503 — 미반영 인스턴스 즉시 식별."""
    from app.database import schema_sync

    client = TestClient(app)
    monkeypatch.setitem(schema_sync, "status", "error")
    monkeypatch.setitem(schema_sync, "error", "table_exists")
    r = client.get("/readyz")
    assert r.status_code == 503
    body = r.json()
    assert body["reason"] == "schema_sync_failed"
    assert body["error"] == "table_exists"

    monkeypatch.setitem(schema_sync, "status", "ok")
    monkeypatch.setitem(schema_sync, "error", None)
    assert client.get("/readyz").status_code == 200


def test_classify_db_error_short_codes():
    """원문 대신 짧은 분류 코드 — 응답·로그 노출 정책과 일치."""
    import sqlalchemy.exc

    from app.database import _classify_db_error

    def operr(msg: str):
        return sqlalchemy.exc.OperationalError("s", {}, Exception(msg))

    cases = [
        (operr("table users already exists"), "table_exists"),
        (operr("no such table: threads"), "no_such_table"),
        (operr("no such column: chat_logs.thread_id"), "no_such_column"),
        (operr("database is locked"), "db_locked"),
        (operr("attempt to write a readonly database"), "db_readonly"),
        (RuntimeError("뭔가 새 종류의 오류"), "RuntimeError"),
    ]
    for exc, expected in cases:
        assert _classify_db_error(exc) == expected


def test_health_exposes_build_fingerprint(monkeypatch):
    """/health.build가 배포 지문(CD 주입 커밋 SHA)을 노출한다(#120).

    CD는 이 필드가 이번 커밋과 일치할 때까지 폴링하여
    '구버전 인스턴스에 새 배포가 통과한 것처럼 보이는' 눈먼 구간을 제거한다.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "build_sha", "abc123def456")
    with TestClient(app) as c:
        body = c.get("/health").json()
    assert body["build"] == "abc123def456"
    assert body["status"] == "ok"
