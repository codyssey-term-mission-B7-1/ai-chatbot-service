"""로그 CLI 클라이언트 회귀 — MockTransport로 API 계약(로그인·필터·커서·권한) 검증."""

import importlib.util
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


def load_client():
    spec = importlib.util.spec_from_file_location(
        "logs_client", ROOT / "scripts" / "logs_client.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_rows(count: int, start_id: int = 1) -> list[dict]:
    rows = []
    for i in range(count):
        rows.append(
            {
                "id": start_id + i,
                "question": f"질문 {start_id + i}",
                "answer": f"응답 {start_id + i}",
                "latency_ms": 100 + i,
                "status": "success" if i % 3 else "ai_error",
                "request_id": f"req-{start_id + i}",
                "created_at": f"2026-09-12T00:{i:02d}:00Z",
            }
        )
    return rows


class FakeServer:
    """로그 API 계약만 구현하는 MockTransport 핸들러."""

    def __init__(
        self,
        rows: list[dict],
        *,
        admin_rows: list[dict] | None = None,
        allow_admin: bool = True,
    ):
        self.rows = rows
        self.admin_rows = (
            admin_rows
            if admin_rows is not None
            else [{**r, "user_id": (i % 2) + 1} for i, r in enumerate(rows)]
        )
        self.allow_admin = allow_admin
        self.login_count = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/auth/login":
            self.login_count += 1
            body = json.loads(request.content)
            if body.get("password") != "Test1234!":
                return httpx.Response(401, json={"detail": "이메일 또는 비밀번호가 달라요."})
            return httpx.Response(
                200,
                json={"email": body["email"], "is_admin": self.allow_admin},
                headers={"Set-Cookie": "session=signed; Path=/"},
            )
        if "session=signed" not in (request.headers.get("cookie") or ""):
            return httpx.Response(401, json={"detail": "로그인이 필요해요."})
        if path == "/api/me/chats":
            limit = int(request.url.params.get("limit", "50"))
            status = request.url.params.get("status")
            before = request.url.params.get("before_id")
            filtered = [r for r in self.rows if before is None or r["id"] < int(before)]
            if status:
                filtered = [r for r in filtered if r["status"] == status]
            filtered.sort(key=lambda r: -r["id"])
            return httpx.Response(200, json=filtered[:limit])
        if path == "/api/admin/chats":
            if not self.allow_admin:
                return httpx.Response(403, json={"detail": "앱 관리자 권한이 필요해요."})
            limit = min(int(request.url.params.get("limit", "50")), 200)
            status = request.url.params.get("status")
            before = request.url.params.get("before_id")
            filtered = [r for r in self.admin_rows if before is None or r["id"] < int(before)]
            if status:
                filtered = [r for r in filtered if r["status"] == status]
            filtered.sort(key=lambda r: -r["id"])
            page = filtered[:limit]
            next_cursor = page[-1]["id"] if len(page) == limit else None
            return httpx.Response(200, json={"items": page, "next_before_id": next_cursor})
        return httpx.Response(404, json={"detail": "Not Found"})


def run_client(capsys, transport: httpx.BaseTransport, *argv: str) -> int:
    module = load_client()
    code = module.main(list(argv), transport=transport)
    return code


def test_my_chats_lists_rows_and_filters_status(capsys):
    rows = make_rows(6)  # id 1..6, status: ai_error, success, success, ai_error, success, success
    transport = httpx.MockTransport(FakeServer(rows).handle)
    client = load_client().make_client("http://test", transport=transport)
    client.post("/api/auth/login", json={"email": "a@b.c", "password": "Test1234!"})

    got = load_client().fetch_my_chats(client, limit=50)
    assert [r["id"] for r in got] == [6, 5, 4, 3, 2, 1]  # 최신순

    only_success = load_client().fetch_my_chats(client, limit=50, status="success")
    assert [r["id"] for r in only_success] == [6, 5, 3, 2]

    paged = load_client().fetch_my_chats(client, limit=2)
    assert [r["id"] for r in paged] == [6, 5]
    next_page = load_client().fetch_my_chats(client, limit=2, before_id=5)
    assert [r["id"] for r in next_page] == [4, 3]
    client.close()


def test_main_my_with_json_output_and_password_stdin(capsys, monkeypatch):
    rows = make_rows(4)
    server = FakeServer(rows)
    argv = ["my", "--base", "http://test", "--email", "a@b.c", "--password-"]
    fake_stdin = type("S", (), {"readline": staticmethod(lambda: "Test1234!\n")})()
    monkeypatch.setattr("sys.stdin", fake_stdin)

    code = run_client(capsys, httpx.MockTransport(server.handle), *argv, "--json")
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert [r["id"] for r in out] == [4, 3, 2, 1]
    assert server.login_count == 1


def test_main_my_pagination_follows_cursor(capsys):
    rows = make_rows(5)  # id 1..5
    code = run_client(
        capsys,
        httpx.MockTransport(FakeServer(rows).handle),
        "my",
        "--base",
        "http://test",
        "--email",
        "a@b.c",
        "--password",
        "Test1234!",
        "--limit",
        "2",
        "--pages",
        "3",
    )
    out = capsys.readouterr().out
    assert code == 0
    lines = [line for line in out.strip().splitlines() if line.startswith("#")]
    ids = [int(line.split("|")[0].lstrip("#")) for line in lines]
    assert ids == [5, 4, 3, 2, 1]  # 2+2+1 — 중복·누락 없음
    assert "(총 5건)" in out


def test_main_admin_uses_page_cursor_and_user_filter(capsys):
    rows = make_rows(6)
    admin_rows = [{**r, "user_id": 1 if r["id"] % 2 else 2} for r in rows]
    code = run_client(
        capsys,
        httpx.MockTransport(FakeServer(rows, admin_rows=admin_rows).handle),
        "all",
        "--base",
        "http://test",
        "--email",
        "a@b.c",
        "--password",
        "Test1234!",
        "--limit",
        "3",
        "--pages",
        "2",
        "--reason",
        "테스트 열람",
    )
    out = capsys.readouterr().out
    assert code == 0
    lines = [line for line in out.strip().splitlines() if line.startswith("#")]
    ids = [int(line.split("|")[0].lstrip("#")) for line in lines]
    assert ids == [6, 5, 4, 3, 2, 1]
    assert "u1" in out and "u2" in out  # 관리자 뷰는 user_id 표시


def test_main_admin_without_permission_exits_1(capsys):
    rows = make_rows(2)
    code = run_client(
        capsys,
        httpx.MockTransport(FakeServer(rows, allow_admin=False).handle),
        "all",
        "--base",
        "http://test",
        "--email",
        "a@b.c",
        "--password",
        "Test1234!",
    )
    err = capsys.readouterr().err
    assert code == 1
    assert "권한이 부족합니다(403)" in err


def test_main_login_failure_exits_1(capsys):
    code = run_client(
        capsys,
        httpx.MockTransport(FakeServer(make_rows(1)).handle),
        "my",
        "--base",
        "http://test",
        "--email",
        "a@b.c",
        "--password",
        "wrong",
    )
    err = capsys.readouterr().err
    assert code == 1
    assert "로그인" in err and "401" in err


def test_main_without_password_exits_2(capsys):
    code = run_client(
        capsys,
        httpx.MockTransport(FakeServer(make_rows(1)).handle),
        "my",
        "--base",
        "http://test",
        "--email",
        "a@b.c",
    )
    assert code == 2
    assert "--password" in capsys.readouterr().err


def test_main_invalid_limit_exits_2(capsys):
    code = run_client(
        capsys,
        httpx.MockTransport(FakeServer(make_rows(1)).handle),
        "my",
        "--base",
        "http://test",
        "--email",
        "a@b.c",
        "--password",
        "Test1234!",
        "--limit",
        "500",
    )
    assert code == 2
    assert "1~200" in capsys.readouterr().err


def test_kst_formatting_in_table(capsys):
    rows = make_rows(1)  # created_at 2026-09-12T00:00:00Z → KST 09:00
    code = run_client(
        capsys,
        httpx.MockTransport(FakeServer(rows).handle),
        "my",
        "--base",
        "http://test",
        "--email",
        "a@b.c",
        "--password",
        "Test1234!",
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "09-12 09:00 KST" in out
