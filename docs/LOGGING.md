# 로그 계약 — 목적·필드·집계

## 형식과 출력

앱 표준 이벤트는 **stderr**에 `시간 레벨 로거 event=이름 key=value ...` 형식으로 기록한다. 로깅 시간은 프로세스의 시간대 기준이며, DB/API 시각의 UTC 계약과 구분한다. 배포 플랫폼은 실제 수집 설정을 확인해야 한다.

- 한 줄에 한 이벤트. 공백·따옴표·줄바꿈이 있는 값은 JSON 문자열 형식으로 이스케이프한다.
- 숫자는 숫자로, 값 없음은 `-`로 표시한다. 단순 공백 split 대신 인용 문자열을 처리하는 파서를 사용한다.
- 질문·답변·실제 이메일·API 키·비밀번호·쿠키를 표준 이벤트에 기록하지 않는다. 해당 이름의 필드는 `[REDACTED]` 처리하며 호출부에서도 원문을 넘기지 않는다.
- `question_chars`, `context_pairs`, 상태·식별자처럼 필요한 메타데이터만 기록한다. DB 오류는 SQL 파라미터가 노출되지 않도록 예외 타입만 기록한다.
- Python/ASGI 서버의 기동·제3자 라이브러리 진단은 별도 출력일 수 있다. 운영 공유 전에 해당 출력도 점검한다.

```bash
# 로컬 로그 파일로 표준 출력·표준 오류를 함께 수집하는 예
uvicorn app.main:app --host 0.0.0.0 --port 8000 > app-local.log 2>&1
```

## 등록된 이벤트 34종

| 이벤트 | 목적 | 주요 필드 / 집계 주의 |
|---|---|---|
| request_received | 요청 유입 추적 | method, path, request_id, **session_user_id**. 서명된 세션 값이며 아직 DB 검증된 ID는 아님 |
| request_finished | 운영 상태·응답 시간 | method, path, status, request_id, **user_id**. 인증 의존성/로그인 검증이 끝난 계정 ID만 기록 |
| ai_call_start | AI 비용·문맥 크기 추적 | user_id, thread_id, request_id, question_chars, context_pairs |
| ai_call_success | 응답 성공·시간 | user_id, request_id, latency_ms |
| ai_call_fail | 장애 진단 | user_id, request_id, reason, latency_ms |
| ai_retry | 추가 시도 집계 | attempt, previous_error, delay_ms. 실제 추가 시도를 시작할 때만 기록 |
| chat_rate_limited | 사용자별 요청 상한 초과 | user_id, retry_after_sec, request_id. AI 호출 없이 429로 종료 |
| db_save_success | 저장 추적 | user_id, chat_id, status, request_id |
| db_save_fail | 저장 장애 | user_id, reason(예외 타입), request_id. 원문/SQL 파라미터 제외 |
| unhandled_error | 예상 밖 서버 오류 | path, error(예외 타입), request_id |
| auth_stale_session | 오래된 세션 파기 | user_id, request_id(HTTP 요청 안이면 자동 부여) |
| auth_session_revoked | 서버 측 폐기 세션 거부 | user_id, request_id. 폐기 기준 이전 발급 세션 차단(#74) |
| user_signup | 계정 생성 추적 | user_id, email_domain. 평문 이메일 제외 |
| signup_rate_limited | IP별 가입 요청 상한 초과 | retry_after_sec, request_id |
| user_login | 성공 로그인 추적 | user_id, request_id |
| user_login_fail | 인증 실패·무차별 대입 징후 | user_id(있으면), email_domain, request_id. 이메일 평문 제외 |
| user_login_locked | 실패 누적 잠금 발동 | email_domain, retry_after_sec, request_id. 이메일 평문 제외 |
| auth_password_rehashed | 레거시 해시 자동 재해싱 | user_id. 페퍼 도입 전 가입자의 다음 로그인 때 기록 |
| admin_logs_viewed | 민감 기록 접근 감사 | user_id(검증된 관리자), filter_user_id, result_count, before_id, request_id |
| admin_hash_status_viewed | 해시 현황 조회 감사 | user_id(검증된 관리자), total, legacy |
| admin_user_deleted | 사용자 삭제 감사 | user_id(검증된 관리자), deleted_user_id, email_domain. 평문 이메일 제외, WARNING |
| thread_created | 대화(스레드) 생성 | user_id, thread_id |
| thread_deleted | 대화(스레드) 삭제 — 기록 CASCADE | user_id, thread_id |
| readyz_db_failure | 기동 시 스키마 동기화 실패 / /readyz의 DB 확인 실패 | error(예외 타입), reason. DB는 살아도 스키마 미반영을 이어서 드러낸다 |
| readyz_schema_failure | /readyz가 스키마 동기화 실패를 발견 | error(예외 타입). 503 응답과 함께 |
| auth_password_reset_requested | 재설정 링크 발급 | user_id, request_id. 토큰 원문 없음 |
| auth_password_reset_rate_limited | 요청 상한 초과로 발송 생략 | user_id, request_id |
| auth_password_reset_ip_rate_limited | IP별 재설정 요청 상한 초과 | retry_after_sec, request_id |
| auth_password_reset_email_sent | 재설정 메일 발송 성공 | user_id, request_id |
| auth_password_reset_email_dev_console | 개발 모드 링크 콘솔 출력 | 링크는 경고 로그에만 |
| auth_password_reset_email_unconfigured | 운영 SMTP 미설정 503 | request_id |
| auth_password_reset_email_failed | 메일 발송 예외 | error 요약, request_id |
| auth_password_reset_rejected | 무효·만료·사용된 토큰 | request_id. 토큰 값 없음 |
| auth_password_reset_completed | 비밀번호 변경 완료 + 세션 전면 폐기 | user_id, request_id |

HTTP 수신 이벤트는 `/api/` 요청당 **1회**다. 채팅 라우트에서 같은 이벤트를 중복 기록하지 않는다. `X-Request-ID` 응답 헤더와 DB `request_id`도 같은 ID를 사용한다. 요청 취소 시 종료 로그의 499는 내부 표기이며 실제 499 응답 전송을 보장하지 않는다.

`ai_call_*`의 latency_ms는 AI 논리 호출 시간(재시도·대기 포함)이며 DB 저장/전체 HTTP 시간은 제외한다. `request_finished`는 HTTP 처리 전체의 시간이다.

## 설명용 예시 — 실제 운영 로그 아님

```text
INFO app event=request_received method=POST path=/api/chat session_user_id=12 request_id=example
INFO app.chat event=ai_call_start user_id=12 question_chars=8 context_pairs=5 request_id=example
WARNING app.ai event=ai_retry request_id=example attempt=2 previous_error=ConnectError delay_ms=500
INFO app.chat event=ai_call_success user_id=12 request_id=example latency_ms=740
INFO app.chat event=db_save_success user_id=12 chat_id=987 status=success request_id=example
INFO app event=request_finished method=POST path=/api/chat user_id=12 status=200 request_id=example latency_ms=752
```

운영 추적·개선 분석에는 이벤트 수와 시도 수, 데모와 실 AI, 정상 응답과 DB 저장 성공을 분리해 사용한다. 로컬 합성 로그와 실제 운영 로그를 같은 증빙으로 제출하지 않는다.
