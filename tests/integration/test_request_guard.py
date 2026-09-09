"""통합 테스트 — CSP 헤더·Origin 검증·운영 문서 게이트(#75)."""

from app.config import settings
from tests.conftest import signup_and_login


def test_security_headers_include_csp(client):
    response = client.get("/health")
    csp = response.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_cross_origin_state_changing_request_is_blocked(client):
    blocked = client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert blocked.status_code == 403
    assert "출처" in blocked.json()["detail"]
    # 차단 응답에도 보안 헤더가 유지된다.
    assert blocked.headers.get("x-content-type-options") == "nosniff"
    assert "default-src 'self'" in blocked.headers.get("content-security-policy", "")


def test_same_origin_and_originless_requests_pass(client):
    signup_and_login(client, email="origin-ok@example.com")
    same = client.post("/api/auth/logout", headers={"Origin": "http://testserver"})
    assert same.status_code == 200
    # Origin을 보내지 않는 클라이언트(curl·스모크)도 통과한다.
    assert client.post("/api/auth/logout").status_code == 200


def test_cross_origin_get_is_not_blocked(client):
    """GET 조회는 CSRF 민감 경로가 아니다 — Origin이 달라도 차단하지 않는다."""
    response = client.get("/api/me/chats", headers={"Origin": "https://evil.example"})
    assert response.status_code == 401  # 인증 오류는 정상 동작, 403(출처)이 아니어야 한다.


def test_docs_available_when_enabled(client, monkeypatch):
    monkeypatch.setattr(settings, "docs_enabled", True)
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_docs_hidden_when_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "docs_enabled", False)
    assert client.get("/docs").status_code == 404
    assert client.get("/docs/").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    # 게이트 밖 경로는 영향이 없다.
    assert client.get("/health").status_code == 200


def test_blocked_api_request_is_still_logged(client, caplog):
    """차단된 요청도 request_finished 로그에 남는다 — 가드가 로깅 안쪽에 있다."""
    import logging

    with caplog.at_level(logging.INFO):
        assert (
            client.post("/api/auth/logout", headers={"Origin": "https://evil.example"}).status_code
            == 403
        )
    assert any(
        "event=request_finished" in r.message and "status=403" in r.message for r in caplog.records
    )
    # 비API 경로(/openapi.json)의 문서 게이트 404는 원래 HTTP 로그 대상이 아니다.
    monkeypatch_docs_off = getattr(settings, "docs_enabled", None)
    settings.docs_enabled = False
    try:
        assert client.get("/openapi.json").status_code == 404
    finally:
        settings.docs_enabled = monkeypatch_docs_off
