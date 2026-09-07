# DB 증빙 패키지 (카드 08)

> `scripts/check_logs.sql` 실행 결과 + 인덱스 검증 + 모델명 필드 결정 기록.
> 실행일: 2026-09-07 · 방법: `seed_mock_data.py`로 시딩 후 동일 SELECT 실행
> (sqlite3 CLI 대신 python sqlite3 사용 — `.print`/`.mode` 제외 쿼리 동일)

## 1. check_logs.sql 실행 결과

### 최근 대화 로그 20건

```
id | user_id | status | latency | question | answer | created_at
------------------------------------------------------------
6 | 2 | ai_error | 2007ms | 타임아웃 강제 발생 테스트 |  | 2026-09-07 12:23:16.583477
5 | 2 | success | 990ms | 타임아웃은 어떻게 되지? | AI_TIMEOUT_SEC(기본 10초)를 초과하면 504와 함께 AI_ | 2026-09-07 12:23:16.583477
4 | 2 | success | 1050ms | SQLite 로그 확인하는 법? | sqlite3 app.db < scripts/check_logs.sql  | 2026-09-07 12:23:16.583474
3 | 1 | success | 1100ms | 컨텍스트는 몇 턴까지 기억해? | 직전 5개의 질문/응답(CONTEXT_TURNS=5)을 프롬프트에 포함해 | 2026-09-07 12:23:16.581629
2 | 1 | success | 980ms | 내가 방금 뭘 물어봤지? | 직전에 'FastAPI로 배포하는 방법 알려줘'를 물어보셨고, uvico | 2026-09-07 12:23:16.581628
1 | 1 | success | 1240ms | FastAPI로 배포하는 방법 알려줘 | uvicorn app.main:app --host 0.0.0.0 으로 실 | 2026-09-07 12:23:16.581624
```

### 사용자별 대화 통계

```
id | email | nickname | total_chats | errors
------------------------------------------------------------
1 | demo@demo.com | 데모유저 | 3 | 0
2 | tester@demo.com | 테스터 | 3 | 1
3 | admin@demo.com | 운영자 | 0 | 0
```

### 특정 사용자 추적 예시 (user_id=1)

```
id | question | answer | created_at
------------------------------------------------------------
3 | 컨텍스트는 몇 턴까지 기억해? | 직전 5개의 질문/응답(CONTEXT_TURNS=5)을 프롬프트에 포함해 문맥을 유지합니다. .env에서 조절할 수 있어요. | 2026-09-07 12:23:16.581629
2 | 내가 방금 뭘 물어봤지? | 직전에 'FastAPI로 배포하는 방법 알려줘'를 물어보셨고, uvicorn 실행 명령과 환경변수 설정을 안내드렸어요. | 2026-09-07 12:23:16.581628
1 | FastAPI로 배포하는 방법 알려줘 | uvicorn app.main:app --host 0.0.0.0 으로 실행하고, 플랫폼(Cloudtype/Render 등)의  | 2026-09-07 12:23:16.581624
```

## 2. 인덱스 선언 검증

`app/models.py` 확인 — TODO 지정 3곳 전부 `index=True`:

| 위치 | 선언 |
|---|---|
| `models.py:18` | `users.email` — `unique=True, index=True` |
| `models.py:32` | `chat_logs.user_id` — `index=True` (FK) |
| `models.py:39` | `chat_logs.created_at` — `index=True` |

`GET /api/me/chats`의 사용자 필터 + 시각 정렬이 인덱스를 타는 구조. 추가 인덱스 불필요.

## 3. 모델명 필드 추가 여부 — 결정: DROP

- 근거 1: 모델은 배포 단위 전역 설정(`AI_MODEL`)이라 행마다 저장할 정보 가치가 낮음
- 근거 2: SQLite는 `create_all`이 기존 테이블을 변경하지 않아 컬럼 추가 시 마이그레이션 별도 필요 — 과제 규모 대비 과함
- 필요 시 `request_id` + 배포 시점 로그로 모델 추적 가능
- 재검토 조건: 요청별 모델 라우팅 도입 시
