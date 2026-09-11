#!/usr/bin/env python3
"""골든 세트 실행기 — scripts/golden_set.json의 케이스를 순차 제출하고 결과를 저장한다.

사용법 (프로젝트 루트에서):
    python scripts/run_golden_set.py --base-url https://운영URL \
        --email goldenset-demo@example.com --password '골든세트계정비밀번호' \
        --out /tmp/golden_results.json --skip G-09

- 계정이 없으면 가입을 시도하고(409면 로그인), 성공한 대화만 문맥에 들어가는 서비스 계약을 그대로 사용한다.
- CHAT_RATE_PER_MIN(기본 10) 대응: 요청 사이 --sleep(기본 7초) 대기, 429면 Retry-After 후 1회 재시도.
- 결과 JSON에는 계정 비밀번호·쿠키를 저장하지 않는다.
- 판정은 이 스크립트가 하지 않는다 — 원문 응답을 기록해 사람/LLM-judge 채점 재료로 쓴다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="골든 세트 실행기")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--set", default="scripts/golden_set.json")
    parser.add_argument("--out", default="golden_results.json")
    parser.add_argument("--sleep", type=float, default=7.0, help="요청 간 대기 초(기본 7 — 분당 10회 제한 대응)")
    parser.add_argument("--skip", nargs="*", default=[], help="제외할 케이스 ID (예: G-09)")
    args = parser.parse_args()

    spec = json.loads(Path(args.set).read_text())
    cases = [c for c in spec["cases"] if c["id"] not in args.skip]
    base = args.base_url.rstrip("/")
    client = httpx.Client(base_url=base, timeout=60.0)

    # 1) 가입(이미 있으면 409) → 2) 로그인으로 쿠키 확보
    signup = client.post(
        "/api/auth/signup",
        json={"email": args.email, "password": args.password, "nickname": "골든세트"},
    )
    if signup.status_code not in (201, 409):
        print(f"가입 실패: {signup.status_code} {signup.text[:200]}", file=sys.stderr)
        return 2
    login = client.post(
        "/api/auth/login", json={"email": args.email, "password": args.password}
    )
    if login.status_code != 200:
        print(f"로그인 실패: {login.status_code}", file=sys.stderr)
        return 2
    print(f"계정 준비 완료 (가입 {signup.status_code} → 로그인 200) — {len(cases)}개 케이스 실행")

    results = []
    for case in cases:
        entry = {"id": case["id"], "category": case["category"], "expect": case["expect"], "turns": []}
        for question in case["turns"]:
            payload = {"question": question}
            for attempt in (1, 2):  # 429 시 Retry-After만큼 대기 후 1회 재시도
                response = client.post("/api/chat", json=payload)
                if response.status_code == 429 and attempt == 1:
                    wait = float(response.headers.get("retry-after", "10"))
                    print(f"  [{case['id']}] 429 — {wait}초 대기 후 재시도")
                    time.sleep(wait + 1)
                    continue
                break
            body = response.json() if response.status_code == 200 else {}
            entry["turns"].append(
                {
                    "question": question,
                    "http_status": response.status_code,
                    "status": body.get("status"),
                    "latency_ms": body.get("latency_ms"),
                    "chat_id": body.get("chat_id"),
                    "answer": body.get("answer", "") if response.status_code == 200 else response.text[:300],
                }
            )
            print(f"  [{case['id']}] HTTP {response.status_code} ({body.get('latency_ms')}ms) {question[:24]}…")
            time.sleep(args.sleep)
        results.append(entry)

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"완료 — {len(results)}개 케이스 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
