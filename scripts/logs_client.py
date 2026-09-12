#!/usr/bin/env python3
"""로그 조회 CLI 클라이언트 — REST API만으로 동작(DB 직접 접근 불필요).

사용법:
  # 내 대화 로그 최신 50건
  python scripts/logs_client.py my --base https://서비스-URL --email me@example.com --password-

  # 성공 기록만 2페이지(최대 100건, 커서 자동 추적)
  python scripts/logs_client.py my --base ... --email ... --password- --status success --pages 2

  # 관리자: 전체 기록 조회(열람 사유는 감사 로그에 기록됨)
  python scripts/logs_client.py all --base ... --email ... --password- --reason "배포 후 영속성 확인"

  # 스크립트 조합용 원문 JSON
  python scripts/logs_client.py my --base ... --email ... --password- --json

비밀번호는 --password-로 표준 입력에서 읽는 것을 권장한다(shell 히스토리에 남지 않음).
세션 쿠키는 프로세스 메모리에만 머물며 디스크에 저장하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

import httpx

KST = timezone(timedelta(hours=9))


class ClientError(RuntimeError):
    """API 호출 실패 — 사용자가 읽을 수 있는 메시지 포함."""


def make_client(
    base_url: str, *, timeout: float = 15.0, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    """base_url 기준 httpx 클라이언트. transport 주입은 테스트용(MockTransport)."""
    return httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport)


def _raise_for_api_error(action: str, response: httpx.Response) -> None:
    if response.is_success:
        return
    detail = ""
    try:
        payload = response.json()
        raw = payload.get("detail")
        if isinstance(raw, str):
            detail = raw
        elif isinstance(raw, list) and raw:
            first = raw[0]
            field = ".".join(str(p) for p in first.get("loc", []) if isinstance(p, str))
            detail = f"{field}: {first.get('msg', '')}".strip(": ")
    except ValueError:
        pass
    if response.status_code == 401:
        raise ClientError(f"{action}: 로그인 필요하거나 로그인 실패(401)") from None
    if response.status_code == 403:
        raise ClientError(
            f"{action}: 권한이 부족합니다(403) — 관리자 API는 명시적 관리자 권한이 필요합니다"
        ) from None
    raise ClientError(
        f"{action}: API 오류 {response.status_code}: {detail or response.text[:200]}"
    ) from None


def login(client: httpx.Client, email: str, password: str) -> None:
    """POST /api/auth/login — 성공 시 세션 쿠키가 클라이언트에 저장된다."""
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    _raise_for_api_error("로그인", response)


def fetch_my_chats(
    client: httpx.Client,
    *,
    limit: int = 50,
    status: str | None = None,
    before_id: int | None = None,
) -> list[dict]:
    """GET /api/me/chats — 본인 기록 최신순. 리스트 반환."""
    params: dict[str, object] = {"limit": limit}
    if status is not None:
        params["status"] = status
    if before_id is not None:
        params["before_id"] = before_id
    response = client.get("/api/me/chats", params=params)
    _raise_for_api_error("내 로그 조회", response)
    return response.json()


def fetch_admin_chats(
    client: httpx.Client,
    *,
    limit: int = 50,
    user_id: int | None = None,
    status: str | None = None,
    before_id: int | None = None,
    reason: str = "",
) -> dict:
    """GET /api/admin/chats — 관리자 전체 조회. {items, next_before_id} 반환."""
    params: dict[str, object] = {"limit": limit}
    if user_id is not None:
        params["user_id"] = user_id
    if status is not None:
        params["status"] = status
    if before_id is not None:
        params["before_id"] = before_id
    if reason:
        params["reason"] = reason
    response = client.get("/api/admin/chats", params=params)
    _raise_for_api_error("관리자 로그 조회", response)
    return response.json()


def paginate(client: httpx.Client, fetch, *, limit: int, pages: int, **kwargs) -> list[dict]:
    """before_id 커서로 여러 페이지를 잇는다. (me=리스트, admin=페이지 객체 둘 다 대응)"""
    rows: list[dict] = []
    cursor = kwargs.pop("before_id", None)
    for _ in range(max(1, pages)):
        batch = fetch(client, limit=limit, before_id=cursor, **kwargs)
        if isinstance(batch, dict):
            items = batch["items"]
            cursor = batch.get("next_before_id")
        else:
            items = batch
            cursor = items[-1]["id"] if items and len(items) == limit else None
        rows.extend(items)
        if not items or cursor is None:
            break
    return rows


def _fmt_kst(iso_utc: str) -> str:
    dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    return dt.astimezone(KST).strftime("%m-%d %H:%M")


def print_rows(rows: list[dict], *, admin: bool) -> None:
    for row in rows:
        parts = [f"#{row['id']}", _fmt_kst(row["created_at"]) + " KST", row["status"]]
        if admin:
            parts.append(f"u{row['user_id']}")
        parts.append(f"{row['latency_ms']}ms")
        question = row["question"]
        parts.append(question if len(question) <= 60 else question[:60] + "…")
        print(" | ".join(parts))
    print(f"(총 {len(rows)}건)")


def _common_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base", required=True, help="서비스 URL (끝의 / 없이)")
    common.add_argument("--email", required=True, help="로그인 이메일")
    common.add_argument("--password", default=None, help="비밀번호 (권장: --password-)")
    common.add_argument(
        "--password-",
        dest="password_stdin",
        action="store_true",
        help="비밀번호를 표준 입력에서 읽음",
    )
    common.add_argument("--limit", type=int, default=50, help="페이지 크기 1~200 (기본 50)")
    common.add_argument("--status", choices=["success", "ai_error"], default=None, help="상태 필터")
    common.add_argument("--before", type=int, default=None, help="이 id 이전부터 조회 (커서)")
    common.add_argument(
        "--pages", type=int, default=1, help="조회할 페이지 수 (커서 자동 추적, 기본 1)"
    )
    common.add_argument("--json", action="store_true", help="원문 JSON 출력")
    common.add_argument("--timeout", type=float, default=15.0, help="요청 타임아웃 초 (기본 15)")
    return common


def main(argv: list[str] | None = None, *, transport: httpx.BaseTransport | None = None) -> int:
    """transport는 테스트 주입용(MockTransport) — 실 동작에서는 None."""
    parser = argparse.ArgumentParser(
        description="로그 API 클라이언트 — REST API로 내/전체 대화 기록 조회"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    common = _common_parser()
    sub.add_parser("my", parents=[common], help="내 대화 로그 조회 (GET /api/me/chats)")
    admin = sub.add_parser(
        "all", parents=[common], help="관리자: 전체 대화 로그 조회 (GET /api/admin/chats)"
    )
    admin.add_argument("--user-id", type=int, default=None, help="사용자 id 필터")
    admin.add_argument(
        "--reason", default="", help="열람 사유 — 감사 로그(admin_logs_viewed)에 기록됨"
    )
    args = parser.parse_args(argv)

    if not 1 <= args.limit <= 200:
        print("오류: --limit은 1~200이어야 해요.", file=sys.stderr)
        return 2
    password = args.password
    if password is None:
        if args.password_stdin:
            password = sys.stdin.readline().rstrip("\n")
        else:
            print("오류: --password 또는 --password- 지정 필요", file=sys.stderr)
            return 2
    if not password:
        print("오류: 비밀번호가 비어요.", file=sys.stderr)
        return 2

    client = make_client(args.base, timeout=args.timeout, transport=transport)
    try:
        login(client, args.email, password)
        common_kwargs = {"status": args.status}
        if args.command == "my":
            rows = paginate(
                client,
                fetch_my_chats,
                limit=args.limit,
                pages=args.pages,
                before_id=args.before,
                **common_kwargs,
            )
        else:
            rows = paginate(
                client,
                fetch_admin_chats,
                limit=args.limit,
                pages=args.pages,
                before_id=args.before,
                user_id=args.user_id,
                reason=args.reason,
                **common_kwargs,
            )
        if args.json:
            json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            print_rows(rows, admin=(args.command == "all"))
        return 0
    except ClientError as err:
        print(f"오류: {err}", file=sys.stderr)
        return 1
    except httpx.HTTPError as err:
        print(f"네트워크 오류: {err}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
