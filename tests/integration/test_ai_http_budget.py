"""실제 HTTPX와 루프백 서버로 전체 deadline 검증. 외부 AI 서비스는 사용하지 않는다."""

import http.server
import json
import threading
import time

import pytest

from app.main import app
from app.services.ai_client import OpenAICompatClient, get_ai_provider
from tests.conftest import signup_and_login


@pytest.mark.parametrize("budget", [0.001, 0.15])
def test_http_total_budget_returns_504_even_when_chunks_keep_arriving(client, budget, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,::1")
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1,::1")
    payload = json.dumps({"choices": [{"message": {"content": "slow local response"}}]}).encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                for index in range(0, len(payload), 6):
                    self.wfile.write(payload[index : index + 6])
                    self.wfile.flush()
                    time.sleep(0.05)  # each gap < 0.15s, whole response > 0.5s
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider = OpenAICompatClient(
            "local-test-only", f"http://127.0.0.1:{server.server_port}/v1", "test-model", budget, 0
        )
        app.dependency_overrides[get_ai_provider] = lambda: provider
        signup_and_login(client)
        start = time.monotonic()
        response = client.post("/api/chat", json={"question": "로컬 HTTP 시간 예산 검증"})
        assert response.status_code == 504 and "AI_TIMEOUT" in response.json()["detail"]
        assert time.monotonic() - start < 1.5
        assert client.get("/health").status_code == 200
        row = client.get("/api/me/chats?limit=1").json()[0]
        assert row["status"] == "ai_error"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
