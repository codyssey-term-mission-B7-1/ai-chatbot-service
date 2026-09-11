"""2026-09-11 외부 평가 대비 하드닝 패치 검증.

- WAL/busy_timeout: SQLite 연결마다 재적용 확인(A-3 — 쓰기 잠금 경합 완화)
- HSTS·Permissions-Policy: 전 응답 보안 헤더 추가(B-6)
- AI 요청 max_tokens/temperature: 서버 정책 고정(C-3 — 응답 길이 폭탄·비용 방어)
- 관리자 열람 감사 로그의 reason 필드(B-1 — 열람 사유 기록)
"""

import sqlite3

from fastapi.testclient import TestClient

from app.config import settings
from app.database import _sqlite_pragmas_on_connect
from app.services.admin import grant_admin
from app.services.ai_client import OpenAICompatClient
from tests.conftest import signup_and_login


def test_sqlite_pragmas_on_file_db(tmp_path, monkeypatch):
    """파일 DB 연결에서 FK·WAL·busy_timeout이 모두 적용된다."""
    from app.config import settings as app_settings

    db_path = tmp_path / "pragma.db"
    monkeypatch.setattr(app_settings, "database_url", f"sqlite:///{db_path}")
    conn = sqlite3.connect(str(db_path))
    _sqlite_pragmas_on_connect(conn, None)
    cur = conn.cursor()
    assert cur.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert cur.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert cur.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    conn.close()


def test_sqlite_pragmas_on_memory_db_skip_wal():
    """:memory:는 WAL을 지원하지 않으므로 시도하지 않는다(다른 프라그마는 적용)."""
    conn = sqlite3.connect(":memory:")
    _sqlite_pragmas_on_connect(conn, None)
    cur = conn.cursor()
    assert cur.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert cur.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    conn.close()


def test_security_headers_include_hsts_and_permissions_policy(client: TestClient):
    response = client.get("/health")
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert "camera=()" in response.headers["permissions-policy"]


def test_ai_payload_pins_max_tokens_and_temperature(monkeypatch):
    monkeypatch.setattr(settings, "ai_max_tokens", 512)
    monkeypatch.setattr(settings, "ai_temperature", 0.2)
    client_ = OpenAICompatClient("key", "https://example.invalid/v1", "m", 1.0, 0)
    payload = client_.build_payload([{"role": "user", "content": "q"}])
    assert payload["max_tokens"] == 512
    assert payload["temperature"] == 0.2
    assert payload["model"] == "m"


def test_admin_view_audit_log_records_reason(client: TestClient, db):
    """관리자 열람 시 reason이 감사 이벤트에 남는다(B-1 — who/what/why 중 why)."""
    signup_and_login(client, "auditor@example.com")
    grant_admin(db, "auditor@example.com")
    response = client.get(
        "/api/admin/chats", params={"reason": "장애 조사 #100 관련 사용자 문의 대응"}
    )
    assert response.status_code == 200
    assert client.get("/api/admin/chats").status_code == 200  # reason 없이도 통과(하위 호환)
