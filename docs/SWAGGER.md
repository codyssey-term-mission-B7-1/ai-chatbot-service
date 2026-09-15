# Swagger / OpenAPI 명세 참고 문서

> **최종 갱신**: 2026-09-14 · 대상 코드: `app/main.py`, `app/routers/*.py`, `app/config.py`
>
> 이 문서는 FastAPI가 자동 생성하는 Swagger UI(`/docs`)·ReDoc(`/redoc`)·OpenAPI 스키마(`/openapi.json`)의 설정·엔드포인트·테스트·운영 정책을 한 곳에 모은다.

---

## 1. 접속 방법

| 경로 | 용도 | 운영 기본 |
|---|---|---|
| `/docs` | Swagger UI (대화형 API 테스트) | **404** |
| `/redoc` | ReDoc (읽기 전용 명세) | **404** |
| `/openapi.json` | OpenAPI 3.1 JSON 스키마 | **404** |

```bash
# 로컬 (DOCS_ENABLED=true 기본값)
uvicorn app.main:app --reload
# → http://localhost:8000/docs

# 운영 — DOCS_ENABLED=true로 임시 활성화하려면 Railway 변수에서 변경 후 재배포
```

---

## 2. 설정

### 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `DOCS_ENABLED` | `true` (코드), **`false`** (운영 CD 동기화) | `false`면 `/docs`·`/redoc`·`/openapi.json` 전부 404 |

### 코드 위치

| 항목 | 파일 | 라인 |
|---|---|---|
| `docs_enabled` 설정 | `app/config.py` | `docs_enabled: bool = True` |
| `DOCS_PATHS` 상수 | `app/main.py` | `frozenset({"/docs", "/docs/", "/redoc", "/redoc/", "/openapi.json"})` |
| 문서 게이트 미들웨어 | `app/main.py` → `request_guard()` | `DOCS_ENABLED=false`면 DOCS_PATHS를 404로 차단 |
| CSP 예외 | `app/main.py` → `security_headers()` | Swagger UI CDN 자산 로드를 위해 `/docs`·`/redoc`만 CSP 제외 |

### 운영에서 문서 접근이 필요한 경우

1. Railway 대시보드 → Variables → `DOCS_ENABLED=true` 설정
2. 재배포 (CD가 자동 동기화하므로 변수 우선)
3. 확인 후 반드시 `false`로 복구

> **보안 정책** (#75): 운영에서 Swagger는 공격 표면을 줄이기 위해 기본 비활성화. CSP `script-src 'self'`가 Swagger UI CDN을 차단하므로, 문서 경로만 CSP에서 예외 처리한다.

---

## 3. 앱 메타데이터

`app/main.py`의 FastAPI 생성자:

```python
app = FastAPI(
    title=settings.app_name,          # "AI Chatbot Service"
    description=DESCRIPTION,           # 처리 순서·인증·문서 링크 포함
    version="0.2.0",
    openapi_tags=[...],
)
```

### `openapi_tags` (Swagger UI 그룹 정렬·설명)

| 태그 | 설명 | 라우터 |
|---|---|---|
| `auth` | 회원가입·서명 쿠키 세션 | `auth.py` |
| `chat` | AI 응답 → DB 저장 시도 → HTTP 응답 | `chat.py` |
| `logs` | 사용자별 대화 조회·성공 문맥 복원 | `logs.py` |
| `admin` | 명시적 관리자 권한이 필요한 전체 조회 | `admin.py` |
| `ops` | 기동 상태 확인. AI 연결 성공을 뜻하지 않음 | (health/readyz) |

> ⚠️ **`threads` 태그 미등록**: `threads.py`가 `tags=["threads"]`를 사용하지만 `openapi_tags`에 `threads`가 없어 Swagger UI에서 설명이 표시되지 않는다. 기능에는 영향 없으나 문서 완성도를 위해 추가 권장.

### `DESCRIPTION` 전문

```
로그인한 사용자의 질문에 AI가 응답하고, 같은 사용자의 성공 Q/A를 문맥으로 사용합니다.

### 처리 순서
질문 검증 → 성공 문맥 조회 → AI 응답 수신 → DB 저장 시도 → 사용자에게 HTTP 응답.
DB 저장 실패 시 status=success라도 chat_id=-1일 수 있습니다.
AI_TIMEOUT_SEC는 AI 호출 전체 예산(재시도/대기 포함)이며 DB 처리 시간은 제외합니다.

### 인증과 관리자
서명된 세션 쿠키를 사용합니다(JWT 아님). API 비로그인은 401, 관리 권한 부족은 403입니다.
관리자 권한은 기본적으로 없으며 서버 운영자의 명시적 부여가 필요합니다.

### 문서
- [API 명세](https://github.com/.../docs/API.md)
- [공통 규칙](https://github.com/.../CONTRIBUTING.md)
- [역할별 작업](https://github.com/.../docs/TODO.md)
```

---

## 4. 전체 엔드포인트 목록

### `auth` 태그 — `app/routers/auth.py`

| 메서드 | 경로 | summary | 주요 responses |
|---|---|---|---|
| POST | `/api/users` | 회원가입 | 201 생성, 409 이미 가입, 422 검증 실패 |
| POST | `/api/session` | 로그인 | 201 발급, 401 불일치, 429 잠금 (Retry-After) |
| POST | `/api/password-resets` | 비밀번호 재설정 요청 | 202 접수, 503 SMTP 미설정, 502 발송 실패 |
| POST | `/api/password-resets/{token}` | 비밀번호 재설정 완료 | 200 완료, 400 토큰 무효 |
| DELETE | `/api/session` | 로그아웃 | 204 (비로그인도 204) |
| GET | `/api/users/me` | 내 정보 | 401 로그인 필요 |

### `chat` 태그 — `app/routers/chat.py`

| 메서드 | 경로 | summary | 주요 responses |
|---|---|---|---|
| POST | `/api/chats` | 질문 → AI 응답 | 201 생성(저장 성공)·200(저장 실패, chat_id=-1), 401 로그인, 404 thread_id 무효, 422 검증, 429 rate limit, 502 AI 오류, 504 타임아웃 |

**처리 순서**: 입력 검증 → thread_id 소유권 검증 → 성공 Q/A 최대 N쌍 → AI 호출 → DB 저장 시도 → 응답.

### `logs` 태그 — `app/routers/logs.py`

| 메서드 | 경로 | summary | 주요 responses |
|---|---|---|---|
| GET | `/api/users/me/chats` | 내 대화 로그 조회 | 401 로그인, 404 thread_id 무효 |

**파라미터**: `status`(success/ai_error), `limit`(1~200, 기본 50), `before_id`(커서), `thread_id`(필터).

### `threads` 태그 — `app/routers/threads.py`

| 메서드 | 경로 | summary | 주요 responses |
|---|---|---|---|
| POST | `/api/thread` | 새 대화 시작 | 401 로그인, 409 상한 도달 |
| GET | `/api/thread/list` | 내 대화 목록 | 401 로그인 |
| GET | `/api/thread/{id}` | 대화 단건 조회 | 401 로그인, 404 부존재/타인 |
| GET | `/api/thread/{id}/chats` | 대화별 기록 | 401 로그인, 404 부존재/타인 |
| DELETE | `/api/thread/{id}` | 대화 삭제(204) | 401 로그인, 404 부존재/타인 |

**상한**: `MAX_THREADS_PER_USER` (기본 100). **삭제**: 해당 스레드의 `chat_logs`도 CASCADE로 함께 삭제.

### `admin` 태그 — `app/routers/admin.py`

| 메서드 | 경로 | summary | 주요 responses |
|---|---|---|---|
| GET | `/api/admin/chats` | 관리자 대화 로그 조회 | 401 로그인, 403 권한 필요 |
| GET | `/api/admin/security/password-hashes` | 비밀번호 해시 마이그레이션 현황 | 401 로그인, 403 권한 필요 |
| DELETE | `/api/admin/users/{id}` | 사용자 삭제 | 400 자기자신/다른 관리자, 401, 403, 404 |

**파라미터** (`/api/admin/chats`): `email`(정확 일치), `status`, `limit`, `before_id`, `reason`(열람 사유 — 감사 로그 기록).

### `ops` 태그 — `app/main.py` (직접 등록)

| 메서드 | 경로 | summary | 설명 |
|---|---|---|---|
| GET | `/health` | 헬스체크 | `status`, `version`, `ai_mode`(real/demo), `build`(SHA), `schema`(ok/error) |
| GET | `/readyz` | 준비성 확인 | 스키마 실패 시 503. DB 장애 시 503 |

### HTML 페이지 — `app/routers/pages.py` (Swagger 태그 없음)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 채팅 페이지 (로그인 필요) |
| GET | `/login` | 로그인/회원가입 |
| GET | `/signup` | 로그인 페이지로 리다이렉트 |
| GET | `/forgot-password` | 비밀번호 찾기 |
| GET | `/reset-password` | 비밀번호 재설정 (토큰 필요) |
| GET | `/logs` | 내 대화 기록 |
| GET | `/admin/logs` | 관리자 로그 조회 |

---

## 5. 인증 방식

- **서명 쿠키 세션** (Starlette `SessionMiddleware`): JWT 아님
- 쿠키 페이로드: `user_id`(int), `email_fp`(이메일 HMAC 지문), `iat`(발급 epoch 초)
- 비로그인 API 호출: **401**
- 관리자 권한 없음: **403**
- 세션 폐기: `session_revocations` 테이블의 `revoked_before_epoch` 이하 `iat` → 거부

---

## 6. 테스트

| 파일 | 테스트 | 검증 내용 |
|---|---|---|
| `test_request_guard.py` | `test_docs_accessible_when_enabled` | `/docs`·`/redoc`·`/openapi.json` → **200** |
| | `test_docs_hidden_when_disabled` | 같은 경로 → **404** (`/docs/` 슬래시 포함) |
| | `test_cross_origin_state_change_blocked` | Origin 불일치 POST → 403, `/openapi.json`은 게이트 대상 |
| `test_verified_gaps.py` | `test_swagger_links_are_absolute_and_descriptions_match_contract` | ① `description`에 GitHub 절대 URL 포함 ② 상대 경로(`../`) 없음 ③ 모든 엔드포인트에 `summary`+`description` 존재 ④ `/api/admin/chats` 경로 존재 |

---

## 7. 관련 이슈·PR 이력

| 이슈/PR | 내용 |
|---|---|
| #38 | Swagger summary/description 보강 요구 |
| #39 | Swagger 보강 PR — 절대 URL·태그·responses 추가 |
| #75 | CSP 도입 → `/docs` 인라인 JS 차단 → Swagger UI CDN 예외 처리, 운영 `/docs` 404 게이트 |
| `test_swagger_links_are_absolute_and_descriptions_match_contract` | 회귀 테스트 — 상대 경로·빈 description 방지 |

---

## 8. 알려진 한계

| 항목 | 현재 상태 | 권장 |
|---|---|---|
| `threads` 태그 미등록 | `openapi_tags`에 없어 Swagger UI 그룹 설명 미표시 | `{"name": "threads", "description": "대화(스레드) 관리 — 생성·목록·삭제"}` 추가 |
| HTML 페이지 Swagger 미등록 | `pages.py` 라우터에 `summary`/`description` 없음 | HTML은 Swagger 대상이 아니므로 의도적 생략 (유지) |
| 운영 Swagger 접근 | `DOCS_ENABLED` 변수 변경 후 재배포 필요 | 긴급 시 Railway Shell에서 환경변수 직접 설정도 가능 |
