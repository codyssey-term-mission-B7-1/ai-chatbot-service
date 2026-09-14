# 설정·상수 분류표 (CONFIG BOUNDARY)

> 판단 기준 한 줄: **환경을 옮기면 바뀌는가?** 예 → ① 환경설정 / 아니오 → ③ 코드 상수.
> 근거 이슈 #152·D-25. 규칙 강제는 `tests/unit/test_config_boundary.py`.

| 분류 | 담는 것 | 위치 | 운영자 변경 |
|---|---|---|---|
| ① 환경설정 (env) | 배포 환경마다 달라지는 비밀값·엔드포인트·스위치 | `.env` → `app/config.py` Settings | 가능 (재시작 적용) |
| ② 기본값 (config default) | ①의 코드 기본값 — 미설정 시 동작 | `app/config.py` Field default | ①을 비우면 적용 |
| ③ 코드 상수 (policy) | 환경과 무관한 불변 정책 | `app/policies.py` | 불가 (코드 변경 필요) |

## ① 환경설정 — 전수 (28키, `.env.example` 표기 따름)

| 키 | 표기 | ② 기본값 | 비고 |
|---|---|---|---|
| SESSION_SECRET | 필수 | 개발 임시키 자동 대체 | 운영 약한 값 → 시작 거부 |
| PASSWORD_PEPPER | 필수 | 개발 임시값 | 운영 미설정 → 시작 거부 |
| DEBUG | 운영 | false | true면 http 쿠키·약한 시크릿 허용 |
| AI_API_KEY | 필수-기능 | None(데모 모드) | |
| AI_BASE_URL / AI_MODEL | 선택 | OpenAI 호환 기본값 | 네이토 사용 시 변경 |
| AI_TIMEOUT_SEC / AI_MAX_RETRIES / AI_MAX_TOKENS / AI_TEMPERATURE | 선택 | 45 / 1 / 800 / 0.6 | |
| DATABASE_URL | 환경별 | sqlite:///./app.db | |
| DOCS_ENABLED | 운영 | true (CD가 false 동기화) | |
| LOGIN_MAX_FAILS / LOGIN_LOCKOUT_SEC | 선택 | 5 / 900 | |
| CHAT_RATE_PER_MIN | 선택 | 10 (0=끔) | |
| CONTEXT_TURNS | 선택 | 5 (상한 200=③) | |
| MAX_QUESTION_LENGTH | 선택 | 1000 | |
| SESSION_MAX_AGE_HOURS | 선택 | 24 (상한 168) | |
| PASSWORD_RESET_EXPIRY_MINUTES / MAX_REQUESTS / WINDOW_MINUTES | 선택 | 30 / 3 / 15 | |
| SMTP_HOST·PORT·USER·PASSWORD·FROM | 선택 | 빈 값(로그 출력/운영 503) | |
| RESEND_API_KEY / RESEND_FROM | 선택 | 빈 값 / onboarding@resend.dev | |

Settings 내부 전용( `.env` 예시에 없음): `app_name`, `build_sha`(CD 주입), `docs_enabled` 제외한 내부 식별용.

## ③ 코드 상수 — 전수 (`app/policies.py`)

| 상수 | 값 | 역할 |
|---|---|---|
| MAX_PASSWORD_CHARS / MIN_PASSWORD_CHARS / MAX_PASSWORD_BYTES | 64 / 8 / 72 | 비밀번호 규칙 (bcrypt 72바이트 한계) |
| MAX_NICKNAME_CHARS / MAX_EMAIL_LOCAL_CHARS | 20 / 64 | 닉네임·이메일 로컬파트 길이 |
| MAX_CONTEXT_TURNS | 200 | 문맥 턴 상한 (환경값 CONTEXT_TURNS의 상한) |
| MAX_LOG_PAGE_SIZE | 200 | 로그 조회 페이지 상한 |
| MAX_THREAD_TITLE_CHARS / DEFAULT_THREAD_TITLE | 20 / 기본 대화 | 스레드 제목 |
| CONTENT_SECURITY_POLICY / SECURITY_HEADERS | — | 보안 헤더(완화 금지) |
| DOCS_PATHS / STATE_CHANGING_METHODS | — | 미들웨어 공용 |
| DEMO_EMAILS | 3종 | 데모 계정 |
| REQUEST_ID_CHARS | 20 | 요청 ID 길이(발급·DB 열 공통) |
| RATE_WINDOW_SECONDS | 60.0 | 분당 리밋터 윈도우 |

환경값으로 만들지 **않는** 이유: 운영자가 함부로 완화하면 안 되는 보안 불변식이기 때문.
