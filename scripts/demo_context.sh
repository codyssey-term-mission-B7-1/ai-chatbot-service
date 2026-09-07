#!/usr/bin/env bash
# 문맥 유지 시연 (#7) — 연속 3턴 대화에서 직전 질문을 인용하는지 검증
# 사용법: ./scripts/demo_context.sh [BASE_URL]   (기본 http://127.0.0.1:8000)
#
# 마지막 턴의 응답에 2번째 질문이 인용되면 통과.
# 원문 인용이 없으면 이 문자열 검사에는 실패한다. 실 AI가 바꿔 말할 수 있으므로 문맥 미전달 여부는 별도 확인한다.
set -euo pipefail
BASE="${1:-http://127.0.0.1:8000}"
EMAIL="ctx_$(date +%s)@example.com"
COOKIE=$(mktemp)
trap 'rm -f "$COOKIE"' EXIT

Q1="FastAPI로 배포하는 방법 알려줘"
Q2="환경변수는 뭐가 필요해?"
Q3="내가 방금 뭘 물어봤지?"

ask() { # ask <질문> → 응답 텍스트 (실패 시 사유 출력 후 1 반환)
  local res status body
  res=$(curl -sS -w $'\n%{http_code}' -b "$COOKIE" -X POST "$BASE/api/chat" \
    -H 'Content-Type: application/json' \
    -d "$(printf '{"question":"%s"}' "$1")")
  status="${res##*$'\n'}"
  body="${res%$'\n'*}"
  if [ "$status" != "200" ]; then
    # 504(타임아웃)/502(AI 오류) 응답은 {"detail": ...} 라 answer 키가 없다.
    # 여기서 멈추지 않으면 이후 턴이 빈 문맥으로 진행돼 엉뚱한 결론이 나온다.
    echo "❌ 채팅 실패 (HTTP $status) — 문맥 검증을 중단합니다." >&2
    echo "   응답: $(printf '%s' "$body" | python3 -c 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read().decode("utf-8")[:200].encode("utf-8"))')" >&2
    return 1
  fi
  printf '%s' "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("answer",""))'
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

# 명령 치환 안의 exit는 서브셸만 끝내므로, 반드시 변수에 담아 실패를 전파한다.
echo "── 1턴 ──"; echo "Q: $Q1"; A1="$(ask "$Q1")" || exit 1; echo "A: $A1"; echo
echo "── 2턴 ──"; echo "Q: $Q2"; A2="$(ask "$Q2")" || exit 1; echo "A: $A2"; echo
echo "── 3턴 ──"; echo "Q: $Q3"; A3="$(ask "$Q3")" || exit 1; echo "A: $A3"; echo

echo "── 저장된 대화 로그 (사용자 기준 추적) ──"
curl -sS -b "$COOKIE" "$BASE/api/me/chats" \
  | python3 -c '
import json, sys
for r in reversed(json.load(sys.stdin)):
    print(f'"'"'  #{r["id"]} [{r["status"]}] {r["latency_ms"]}ms {r["created_at"]}  Q: {r["question"]}'"'"')'
echo

if [[ "$A3" == *"$Q2"* ]]; then
  echo "🎉 통과 — 3턴째 응답이 직전 질문 '$Q2'을(를) 인용했습니다. 이전 질문의 원문 인용 조건 충족."
else
  echo "❌ 실패 — 3턴째 응답에 직전 질문이 인용되지 않았습니다. 컨텍스트 미전달 의심."
  exit 1
fi
