# 문맥 유지 시연 증빙 (#7)

> 완료 조건: **연속 3질문 이상에서 문맥 유지 시연 성공**
> 재현 스크립트: `scripts/demo_context.sh` · 실행일: 2026-09-07

## 1. 무엇을 검증하는가

`POST /api/chat`은 매 요청마다 같은 사용자의 **직전 N개(`CONTEXT_TURNS`, 기본 5) Q/A**를
프롬프트에 실어 AI에 보낸다 (`app/services/context.py:build_context`).

이 스크립트는 3턴째 답변에 2턴째 질문이 원문 그대로 포함되는지 검사한다.
원문 인용이 없으면 종료코드 1로 실패한다. 실 AI는 같은 내용을 바꿔 말할 수 있으므로,
이 실패만으로 문맥 미전달을 단정하지 않는다. 실제 전달 messages와 답변의 의미는 별도로 확인한다.

## 2. 재현 방법

```bash
# 1) 목업 AI 서버 (실제 키 없이 검증 — 네이토 OpenAI 호환 시뮬레이터)
python scripts/mock_openai_server.py          # :8001

# 2) .env 를 목업으로 연결
#    AI_API_KEY=mock-key / AI_BASE_URL=http://127.0.0.1:8001/v1 / AI_MODEL=neito-1

# 3) 앱 서버
uvicorn app.main:app --port 8000

# 4) 시연
./scripts/demo_context.sh http://127.0.0.1:8000
```

> 실제 네이토 키가 준비되면 `.env`의 `AI_BASE_URL`/`AI_MODEL`/`AI_API_KEY`만 바꿔
> 같은 스크립트를 그대로 돌리면 된다 (카드 #6).

## 3. 실행 결과

```
════ 문맥 유지 시연 (#7) — CONTEXT_TURNS 기준 직전 Q/A 전달 ════
대상: http://127.0.0.1:8800

✅ 가입·로그인 완료 (ctx_1788766431@example.com)

── 1턴 ──
Q: FastAPI로 배포하는 방법 알려줘
A: [네이토 mock 응답] 'FastAPI로 배포하는 방법 알려줘'에 대한 답변입니다. (model=neito-1, 컨텍스트 0건 반영)

── 2턴 ──
Q: 환경변수는 뭐가 필요해?
A: [네이토 mock 응답] '환경변수는 뭐가 필요해?'에 대한 답변입니다. (model=neito-1, 컨텍스트 1건 반영)

── 3턴 ──
Q: 내가 방금 뭘 물어봤지?
A: 직전에 '환경변수는 뭐가 필요해?'을(를) 물어보셨어요. 그때 드린 답변을 바탕으로 이어서 설명드릴게요. (네이토 mock 문맥 응답)

── 저장된 대화 로그 (사용자 기준 추적) ──
  #1 [success] 36ms 2026-09-07T07:33:51.663764  Q: FastAPI로 배포하는 방법 알려줘
  #2 [success] 5ms 2026-09-07T07:33:51.682125  Q: 환경변수는 뭐가 필요해?
  #3 [success] 5ms 2026-09-07T07:33:51.702969  Q: 내가 방금 뭘 물어봤지?

🎉 통과 — 3턴째 응답이 직전 질문 '환경변수는 뭐가 필요해?'을(를) 인용했습니다. 문맥 유지 확인.
```

**핵심 근거 2가지**

1. 목업이 보고한 **컨텍스트 반영 건수가 0 → 1로 누적** — 턴이 쌓일수록 프롬프트에 과거 Q/A가 더 실린다.
2. 3턴째 응답이 **2턴째 질문 문자열을 그대로 인용** — 컨텍스트 없이는 불가능한 응답.

## 4. 서버 로그 이벤트 (파이프라인 추적)

`request_id`로 한 요청의 전 구간을 추적할 수 있다.

```
event=request_received  user_id=1 path=/api/chat request_id=567fc45c question=환경변수는 뭐가 필요해?
event=ai_call_start     user_id=1 request_id=567fc45c
event=ai_call_success   request_id=567fc45c latency_ms=5
event=db_save_success   user_id=1 chat_id=2 status=success
```

3턴 전체가 동일한 순서로 기록되며, 질문은 로그 컨벤션대로 50자에서 잘린다.

## 5. DB 저장 확인 (#8 연계)

```
$ sqlite3 demo.db < scripts/check_logs.sql

── 최근 대화 로그 20건 ──
id  user_id  status   latency  question                        created_at
--  -------  -------  -------  ------------------------------  --------------------------
3   1        success  5ms      내가 방금 뭘 물어봤지?          2026-09-07 07:33:51.702969
2   1        success  5ms      환경변수는 뭐가 필요해?         2026-09-07 07:33:51.682125
1   1        success  36ms     FastAPI로 배포하는 방법 알려줘  2026-09-07 07:33:51.663764
```

질문·응답·소요시간·**사용자 식별(user_id)**·**시각(UTC)** 이 전부 저장되어
추적 가능성 요구사항을 충족한다.

## 6. 관련 유닛 테스트

`tests/unit/test_context.py` — 최근 N개만 선택 / 오래된 순서 유지 / 빈 히스토리 처리 3종 통과.

## 7. 반대 케이스 — 검증이 실제로 동작하는지 확인

시연이 "항상 통과하는 스크립트"가 아님을 보이기 위해 컨텍스트를 꺼서 실패를 재현했다.

```bash
# .env: CONTEXT_TURNS=0  (직전 Q/A를 프롬프트에 싣지 않음)
$ ./scripts/demo_context.sh http://127.0.0.1:8000
── 3턴 ──
Q: 내가 방금 뭘 물어봤지?
A: [네이토 mock 응답] '내가 방금 뭘 물어봤지?'에 대한 답변입니다. (model=neito-1, 컨텍스트 0건 반영)

❌ 실패 — 3턴째 응답에 직전 질문이 인용되지 않았습니다. 컨텍스트 미전달 의심.
$ echo $?
1
```

세 턴 모두 "컨텍스트 0건 반영"으로 고정되고 인용이 사라진다.
즉 3절의 통과 결과는 **컨텍스트 전달 여부에 실제로 반응한 결과**다.
