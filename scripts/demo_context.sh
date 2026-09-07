#!/usr/bin/env bash
# 문맥 유지 시연 (#7) — 연속 3턴 대화에서 직전 질문을 인용하는지 검증
# 사용법: ./scripts/demo_context.sh [BASE_URL]   (기본 http://127.0.0.1:8000)
#
# 마지막 턴의 응답에 2번째 질문이 인용되면 통과.
# 인용이 없으면 컨텍스트가 AI에 전달되지 않은 것이므로 실패로 종료한다.
set -euo pipefail
BASE="${1:-http://127.0.0.1:8000}"
EMAIL="ctx_$(date +%s)@example.com"
COOKIE=$(mktemp)
trap 'rm -f "$COOKIE"' EXIT

Q1="FastAPI로 배포하는 방법 알려줘"
Q2="환경변수는 뭐가 필요해?"
Q3="내가 방금 뭘 물어봤지?"

ask() { # ask <질문> → 응답 텍스트
  curl -sS -b "$COOKIE" -X POST "$BASE/api/chat" \
    -H 'Content-Type: application/json' \
    -d "$(printf '{"question":"%s"}' "$1")" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["answer"])'
}

echo "════ 문맥 유지 시연 (#7) — CONTEXT_TURNS 기준 직전 Q/A 전달 ════"
echo "대상: $BASE"
echo

curl -sS -X POST "$BASE/api/auth/signup" -H 'Content-Type: application/json' \
     -d "{\"email\":\"$EMAIL\",\"password\":\"Test1234!\"}" > /dev/null
curl -sS -c "$COOKIE" -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' \
     -d "{\"email\":\"$EMAIL\",\"password\":\"Test1234!\"}" > /dev/null
echo "✅ 가입·로그인 완료 ($EMAIL)"
echo

echo "── 1턴 ──"; echo "Q: $Q1"; echo "A: $(ask "$Q1")"; echo
echo "── 2턴 ──"; echo "Q: $Q2"; echo "A: $(ask "$Q2")"; echo
echo "── 3턴 ──"; echo "Q: $Q3"
A3="$(ask "$Q3")"; echo "A: $A3"; echo

echo "── 저장된 대화 로그 (사용자 기준 추적) ──"
curl -sS -b "$COOKIE" "$BASE/api/me/chats" \
  | python3 -c '
import json, sys
for r in reversed(json.load(sys.stdin)):
    print(f'"'"'  #{r["id"]} [{r["status"]}] {r["latency_ms"]}ms {r["created_at"]}  Q: {r["question"]}'"'"')'
echo

if [[ "$A3" == *"$Q2"* ]]; then
  echo "🎉 통과 — 3턴째 응답이 직전 질문 '$Q2'을(를) 인용했습니다. 문맥 유지 확인."
else
  echo "❌ 실패 — 3턴째 응답에 직전 질문이 인용되지 않았습니다. 컨텍스트 미전달 의심."
  exit 1
fi
