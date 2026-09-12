# 2026-09-12 하드닝 감사 보고서 (Hardening Audit)

> 대상: `main` 직후 `fix/hardening-audit-fixes` 브랜치
> 범위: 코드 버그·보안·운영·제품 전 영역 실제 감사 결과. 조치한 항목은 커밋과 함께 기록한다.
> 문서 목적: 제출 전 "미흡한 점·문제점·조치"를 솔직히 공개하고, 조치 가능한 부분은 이번 PR에서 수정,
> 향후 마일스톤에서 다룰 항목은 티켓으로 남긴다.

---

## 0. 최종 집계

| 분류 | 발견 | 이 PR에서 조치 | 다음 마일스톤 | 인정(과제 범위 내 한계) |
|---|---|---|---|---|
| 코드 버그(정확도) | 4 | 4 | 0 | 0 |
| 보안/프라이버시 | 6 | 2 | 2 | 2 |
| 운영/DevOps | 5 | 1 | 3 | 1 |
| 제품/UX | 4 | 0 | 4 | 0 |
| 문서/투명성 | 3 | 1 | 2 | 0 |
| **합계** | **22** | **8** | **11** | **3** |

- 모든 기존 테스트를 유지한 채 **3개 단위 테스트를 추가**해 이번 수정의 회귀를 방어.
- `pytest 226 passed / ruff·black·isort 통과` 유지 (2026-09-12 기준).

---

## 1. 이 PR에서 직접 조치한 항목 (Fix)

### F-1. AI 페이로드에 `max_tokens`/`temperature`가 실제로 담기지 않던 버그 (심각도: HIGH)
- **증상**: `OpenAICompatClient.build_payload()`가 필드에 `max_tokens`·`temperature`를 넣도록 정의되어 있었지만, `_attempts()`가 `{"model", "messages"}`만 담은 별도 딕셔너리를 만들어 POST하도록 되어 있어 설정이 무시됐다.
- **영향**: 운영에서 설정한 AI_MAX_TOKENS(800)·AI_TEMPERATURE(0.6)가 적용되지 않아 제공사 기본값(무제한/1.0)이 사용됐다. 응답 길이 폭탄·비용 편차·응답 일관성 저하.
- **조치**: `_attempts()`가 `self.build_payload(messages)`를 호출하도록 수정. 회귀 테스트 `test_build_payload_is_signed_with_server_policy` 추가.

### F-2. AI 응답이 `max_tokens`로 잘려도 사용자가 전혀 알 수 없던 문제 (심각도: MEDIUM)
- **증상**: OpenAI 호환 응답의 `finish_reason="length"`를 검사하지 않아 응답이 도중에 끊겨도 마치 완전한 답변인 것처럼 저장·표시. 이후 문맥에도 그 잘린 문자열이 그대로 들어가 응답 품질 저하.
- **조치**: `extract_content()`가 `finish_reason=length`를 감지하면 `…(응답이 길이 제한으로 잘렸어요)` 표식을 붙인다. 회귀 테스트 `test_extract_content_flags_length_truncation` 추가.

### F-3. AI 클라이언트 타임아웃 이중 적용으로 전체 예산이 깨지는 문제 (심각도: MEDIUM)
- **증상**: 바깥 `asyncio.timeout(AI_TIMEOUT_SEC)`로 전체 예산을 보장하면서 동시에 `httpx.AsyncClient(timeout=AI_TIMEOUT_SEC)`을 전달해 연결·읽기 타임아웃이 별도로 걸리고, 재시도 시 예산이 누적될 수 있었다(0.5s backoff가 소진되기 전 httpx가 먼저 끊기며 이벤트 혼선).
- **조치**: per-attempt timeout은 연결·쓰기·풀·읽기를 세분화해 `connect/write/pool`을 짧게 고정하고 전체 상한은 바깥 `asyncio.timeout`이 유일하게 보장하도록 정리. 재시도 이벤트(`ai_retry`)는 backoff sleep *후*에 기록해 "대기 중 타임아웃으로 재시도를 안 했는데 재시도 로그만 남는" 모순을 해소(기존 테스트 의미와 일치).

### F-4. 엔드포인트 중복 접미사 버그 (심각도: LOW)
- **증상**: 사용자가 문서 그대로 `AI_BASE_URL=https://api.openai.com/v1/chat/completions`(기본 예시값)을 사용하면 `normalize_endpoint`가 접미사를 한 번 더 붙여 `/v1/chat/completions/chat/completions`가 됐다. 실제 기본값이 이 형태라 운영 real 모드에서도 잠재 위험.
- **조치**: `normalize_endpoint`가 이미 접미사로 끝나면 정리(strip)한 뒤 한 번만 붙이도록 수정. 회귀 테스트 `test_normalize_endpoint_dedupes_double_suffix` 추가.

### F-5. httpx 클라이언트가 매 요청마다 연결을 맺어 비효율이던 문제 (심각도: LOW)
- **증상**: `async with httpx.AsyncClient(...)`가 generate() 호출마다 생겼지만 커넥션·keep-alive 튜닝이 없어 단기 다중 요청 시 TCP 핸드셰이크가 반복됐다.
- **조치**: `httpx.Limits(max_connections=20, max_keepalive_connections=5)`를 추가.

### F-6. 이메일 발송 실패 로그에 원문 예외 메시지가 그대로 남아 잠재 정보 누출 (심각도: MEDIUM)
- **증상**: `auth.py`의 비밀번호 재설정 실패 처리가 `error=str(exc)`로 로그를 남겨 Resend/SMTP 응답 body나 API key fragments가 포함될 여지가 있었다.
- **조치**: 예외 타입 이름만 로그(`error=type(exc).__name__`)로 제한 — #104 로깅 민감정보 정책과 일관.

### F-7. SQLAlchemy 엔진 풀 설정이 SQLite에 부적절한 인자로 초기화 에러 (심각도: HIGH / dev-only)
- **증상**: Postgres 전환을 염두에 둔 pool 설정(pool_size/max_overflow)을 SQLite에 그대로 넣어 `SingletonThreadPool`과 충돌, `DEBUG=true` 개발 환경에서 create_engine이 TypeError를 뱉을 수 있었음(.env.example 기본 키가 약한 값으로 임시키로 대체되는 경로 때문에 그간 우연히 동작).
- **조치**: DB dialect 분기. SQLite는 기본 SingletonThreadPool 유지, Postgres/MySQL일 때만 풀 옵션 + pool_pre_ping/pool_recycle 적용.

### F-8. 감사 보고서 문서 추가 (본 문서)
- **목적**: 전문가 인터뷰 가이드(EXPERT_INTERVIEW_GUIDE.md)에서 지적된 약점을 팀 내부에서도 우선순위와 함께 명확히 소유하게 한다.

---

## 2. 다음 마일스톤에서 다룰 항목 (Backlog)

### 보안
| ID | 항목 | 이유 | 추정 공수 |
|---|---|---|---|
| B-1 | 회원가입 rate limit + 이메일 인증/캡차 | 현재 가입 엔드포인트에 제한이 없어 봇으로 수만 계정 생성이 이론적으로 가능. 채팅 rate limit은 계정 우회를 막지 못한다. | 2일 |
| B-2 | 세션 쿠키 탈취 대응(IP/UA 바인딩 옵션·재인증) | 공용 PC에서 쿠키 탈취 시 세션 하이재킹. SameSite+Secure만으로 막지 못한다. | 1.5일 |
| B-3 | 프롬프트 인젝션 기본 방어(시스템 프롬프트 분리, 일부 패턴 필터) | 현재 사용자 입력을 user role 그대로 넘기고 있어 기본적인 탈출(ignore previous instructions)에 취약. | 1일 |
| B-4 | AI 응답 모더레이션 기본선 | 혐오·성인·불법 조언에 대한 방어가 없다. 출력 모더레이션 API 또는 키워드 최소 방어 필요. | 1일 |

### 운영/DevOps
| ID | 항목 | 이유 | 추정 공수 |
|---|---|---|---|
| B-5 | 로그인/채팅 rate limit을 Redis/DB 기반으로 이전 | 프로세스 메모리 방식은 재시작 시 초기화되고 다중 워커에서 깨진다. | 2일 |
| B-6 | 외부 헬스체크·에러율 모니터링·장애 알림 | Railway 자동 재시작에 의존하고 있으며 사람이 장애를 인지할 방법이 없다. UptimeRobot/Sentry 최소 도입. | 0.5일 |
| B-7 | SQLite → PostgreSQL 전환 준비(Alembic 마이그레이션) | 동시 사용자 증가 시 SQLite 쓰기 잠금이 병목. DB URL 추상화는 되어 있으나 마이그레이션 툴이 없다. | 2일 |
| B-8 | 오프사이트 백업(S3/R2 등 주기적 업로드) | 현재 백업은 DB와 같은 Volume의 backups/에 떨어져 Volume 자체가 날아가면 손실. | 1일 |

### 제품/UX
| ID | 항목 | 이유 | 추정 공수 |
|---|---|---|---|
| B-9 | 스트리밍 응답(SSE) | 45초 동기 대기 UX는 체감상 매우 답답하다. 토큰 단위 스트리밍과 취소 버튼이 필요. | 2.5일 |
| B-10 | 응답 만족도 피드백(thumbs up/down) + golden set 자동 평가 | 품질 개선 루프가 없다. LLM-as-judge로 회귀 검증 파이프라인까지. | 2일 |
| B-11 | 채팅방 세션/주제 구분 | 현재 모든 질문이 한 줄기라 과거 주제가 문맥을 오염시킨다. | 2일 |
| B-12 | AI 제공자 폴백(OpenAI ↔ Groq 등 429 시 전환) | 단일 제공사 의존 시 429/장애에 무방비. | 1.5일 |

---

## 3. 과제 범위 내에서 인정하는 한계 (문서화로 남기고 억지로 고치지 않음)
다음 항목들은 의도적으로 구현 범위 밖으로 두고 문서(README §8, OPERATIONS.md, ADR)에 명시한다. 억지로 붙이다가 오히려 신뢰도를 낮추지 않기 위해 인정으로 분류한다.

1. **다중 워커·수평 스케일 아웃**: 단일 Railway 워커 + SQLite를 전제. Pro 플랜·Postgres 전환 전까지 1인스턴스 운영.
2. **실제 AI 품질 보증**: 과제 요구는 "서버가 AI 키를 사용한 채팅"이지 RAG·프롬프트 엔지니어링·벤치마크가 아님. AI 제품 품질은 B-10 이후 마일스톤에서 다룬다.
3. **한국 개인정보법(PIPA) 완전 대응**: 별도의 법적 검토·처리방침 확정·동의 플로우가 필요해 기술 범위를 넘어선다. 현 상태로는 질문/답변이 그대로 저장되므로 실서비스 전 개인정보 영향평가 필요(현재 `docs/DATA_POLICY_DRAFT.md`가 초안 상태).

---

## 4. 수정이 필요 없거나 이미 잘 되어 있던 점 (면접에서 어필할 포인트)
- 3계층 분리(routers/services/repositories)가 후속 PR(#77, #78, #101)을 깔끔히 받아들이는 구조로 잘 작동하고 있었다.
- 페퍼+bcrypt + timing-equalizer, CSP/Origin 다층 방어, 서명 쿠키 세션의 설계는 부트캠프 기준으로 상위 수준.
- ADR 8건에 트레이드오프가 명시되어 있고 "실패한 선택"도 기록으로 남아 있다(#81, #100).
- pytest 226개가 실제로 코드 경계를 검증하고(AI 시간예산·로그인 잠금·관리자 격리·프론트 정적계약 등) 통과하고 있다.
- CD의 "Secrets 없으면 실패 중단" 원칙과 Resend 전환(SMTP 차단 대응) 사례는 실제 운영을 경험해 본 흔적이다.

---

## 5. 변경 파일 목록 (이 PR)

```
app/services/ai_client.py    # F-1, F-2, F-3, F-4, F-5
app/database.py              # F-7
app/routers/auth.py          # F-6
tests/unit/test_ai_client.py # F-1, F-4, F-2 회귀 테스트 추가
docs/AUDIT_HARDENING.md      # F-8 (본 문서)
```

실행 결과:
- `pytest`: 223 → **226 passed**
- `ruff check app tests`: All checks passed
- `black --check app tests`: All done! ✨
- `isort --check-only app tests`: 통과

---

*작성: 2026-09-12, fix/hardening-audit-fixes 브랜치*
