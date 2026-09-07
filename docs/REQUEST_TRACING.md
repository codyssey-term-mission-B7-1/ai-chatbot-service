# Request 추적 가이드 (카드 11)

> 한 채팅 요청의 수명주기: 로그 6종 + DB 1행이 `request_id`로 연결된다.

## 흐름

1. `POST /api/chat` 수신 → `request_id = uuid4().hex[:8]` 발급 (`chat.py:61`)
2. 파이프라인 로그 — 전부 동일 `request_id` 포함:
   `request_received` → `ai_call_start` → (`ai_call_success` | `ai_call_fail`) →
   (`db_save_success` | `db_save_fail`) → `request_finished`
3. `chat_logs` 테이블에 동일 `request_id` 저장 (`models.py:37`)

인증 이벤트(`user_signup`·`user_login`)는 채팅 파이프라인 밖이라
`request_id` 대신 `user_id`·`email`로 연결한다.

## 추적 레시피

```bash
# 한 요청의 전체 로그 (8자리 ID로 grep)
grep "request_id=a1b2c3d4" app.log

# 특정 요청의 DB 행
sqlite3 app.db "SELECT id, status, latency_ms FROM chat_logs WHERE request_id = 'a1b2c3d4';"

# AI 실패만 모아보기
grep "event=ai_call_fail" app.log

# DB 저장 실패 (로그-DB 불일치 후보)
grep "event=db_save_fail" app.log
```

## 민감정보 정책

- 질문은 `truncate()`로 최대 50자까지만 로그 (`logging_config.py`)
- API 키·비밀번호·세션 토큰은 절대 로그 금지
- 단, 질문 원문은 DB `chat_logs.question`에 전문 저장 (본인 조회용)

## 미해결 (사람 결정 필요)

- `setup_logging()` + uvicorn 로거 설정 중복 여부 — 배포 환경에서 로그 포맷 실측 후 결정
  (`main.py:16` 호출 순서 의존이 있어 자동 판단 불가)
