#!/usr/bin/env bash
# E2E 스모크 테스트 — 배포된 실서버 대상 전체 흐름 점검
# 사용법: ./scripts/e2e_smoke.sh https://배포URL
set -euo pipefail
BASE="${1:?사용법: ./scripts/e2e_smoke.sh <BASE_URL>}"
EMAIL="smoke_$(date +%s)@example.com"
COOKIE=$(mktemp)
trap 'rm -f "$COOKIE"' EXIT

step() { # step <이름> <기대status> <curl인자...>
  local name="$1"; local expect="$2"; shift 2
  local body status
  body=$(curl -sS -w '\n%{http_code}' "$@" 2>&1) || { echo "$body"; echo "❌ $name — 요청 실패"; exit 1; }
  status="${body##*$'\n'}"
  body="${body%$'\n'*}"
  if [ "$status" != "$expect" ]; then
    echo "❌ $name — 기대 $expect, 실제 $status"
    echo "$body" | python3 -c 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read().decode("utf-8")[:400].encode("utf-8"))'; echo
    exit 1
  fi
  echo "✅ $name ($status)"
  LAST_BODY="$body"
}

step "① 헬스체크"            200 "$BASE/health"
# 스키마 동기화 확인 — 2026-09-13 사고(마이그레이션 미반영 500) 이후 게이트.
# /health는 200을 유지하므로 schema 필드가 ok가 아닌지 여기서 막는다.
SCHEMA=$(echo "$LAST_BODY" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("schema","missing"))')
if [ "$SCHEMA" != "ok" ]; then
  echo "❌ 스키마 동기화 실패 — schema=$SCHEMA (Railway 로그의 init_db/readyz_schema_failure 확인)"
  exit 1
fi
echo "    └ 스키마 동기화: ok"
step "② 회원가입 ($EMAIL)"    201 -X POST "$BASE/api/auth/signup" -H 'Content-Type: application/json' \
     -d "{\"email\":\"$EMAIL\",\"password\":\"Test1234!\"}"
step "③ 로그인 (쿠키 발급)"    200 -c "$COOKIE" -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' \
     -d "{\"email\":\"$EMAIL\",\"password\":\"Test1234!\"}"
step "④ 미로그인 채팅 차단"    401 -X POST "$BASE/api/chat" -H 'Content-Type: application/json' \
     -d '{"question":"hi"}'
step "⑤ 빈 입력 검증 (422)"   422 -b "$COOKIE" -X POST "$BASE/api/chat" -H 'Content-Type: application/json' \
     -d '{"question":"   "}'
step "⑥ 채팅 (AI 호출)"       200 -b "$COOKIE" -X POST "$BASE/api/chat" -H 'Content-Type: application/json' \
     -d '{"question":"안녕, 한 줄로 자기소개해줘"}'
echo "    └ 응답: $(echo "$LAST_BODY" | python3 -c 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read().decode("utf-8")[:200].encode("utf-8"))')"
step "⑦ 내 대화 로그 조회"     200 -b "$COOKIE" "$BASE/api/me/chats"
echo "    └ 로그: $(echo "$LAST_BODY" | python3 -c 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read().decode("utf-8")[:200].encode("utf-8"))')"
step "⑧ 새 대화 시작 (스레드)"  201 -b "$COOKIE" -X POST "$BASE/api/threads"
TID=$(echo "$LAST_BODY" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
step "⑨ 새 대화 채팅 (thread_id)" 200 -b "$COOKIE" -X POST "$BASE/api/chat" -H 'Content-Type: application/json' \
     -d "{\"question\":\"새 대화 스모크 질문입니다.\",\"thread_id\":$TID}"
step "⑩ 새 대화 로그 조회 (필터)"  200 -b "$COOKIE" "$BASE/api/me/chats?thread_id=$TID"
echo "    └ 스레드 $TID 로그: $(echo "$LAST_BODY" | python3 -c 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read().decode("utf-8")[:200].encode("utf-8"))')"

echo ""
echo "🎉 E2E 스모크 통과 — $(date)"
