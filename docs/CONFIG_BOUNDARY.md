# 설정·상수 분류표 (CONFIG BOUNDARY)

> 판단 기준 한 줄: **환경을 옮기면 바뀌는가?** 예 → ① 환경설정 / 아니오 → ③ 코드 상수.
> 근거 이슈 #152·D-25. 규칙 강제는 `tests/unit/test_config_boundary.py`.

| 분류 | 담는 것 | 위치 | 운영자 변경 |
|---|---|---|---|
| ① 환경설정 (env) | 배포 환경마다 달라지는 비밀값·엔드포인트·스위치 | `.env` → `app/config.py` Settings | 가능 (재시작 적용) |
| ② 기본값 (config default) | ①의 코드 기본값 — 미설정 시 동작 | `app/config.py` Field default | ①을 비우면 적용 |
| ③ 코드 상수 (policy) | 환경과 무관한 보안·도메인·인프라 불변 정책 | `app/policies.py` | 불가 (코드 변경 필요) |

---

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

Settings 내부 전용( `.env` 예시에 없음): `app_name`, `build_sha`(CD 주입), `docs_enabled`, `rate_window_seconds`(기본 60초), `admin_log_keep_rows`(기본 5000), `default_page_size`(기본 50).

---

## ③ 코드 상수 — 전수 (`app/policies.py`의 5대 영역 체계화)

불변 정책은 성격에 따라 5대 범주로 체계화되어 있습니다:

### 1. 암호학적 및 보안 불변 정책 (Cryptographic & Security Invariants)
| 상수 | 값 | 역할 |
|---|---|---|
| MAX_PASSWORD_BYTES | 72 | bcrypt 해시 함수 최대 바이트 한계 (잘림 취약점 원천 방지) |
| REQUEST_ID_CHARS | 20 | 분산 추적용 UUID 슬라이스 길이 (발급/DB 컬럼 공통) |
| DEMO_EMAILS | 3종 | 공개 패스워드를 사용하는 데모 계정 (관리자 승격 원천 차단) |

### 2. 도메인 데이터 검증 규칙 (Domain Validation Rules)
| 상수 | 값 | 역할 |
|---|---|---|
| MIN_PASSWORD_CHARS / MAX_PASSWORD_CHARS | 8 / 64 | 비밀번호 글자수 제약 |
| MAX_NICKNAME_CHARS | 20 | 사용자 닉네임 최대 길이 |
| MAX_EMAIL_LOCAL_CHARS | 64 | 이메일 로컬파트(@ 앞부분) 최대 길이 |
| MAX_THREAD_TITLE_CHARS / DEFAULT_THREAD_TITLE | 20 / "기본 대화" | 스레드 제목 규격 및 기본명 |

### 3. 시스템 안전 한계 상한선 (System Safety Ceilings)
| 상수 | 값 | 역할 |
|---|---|---|
| MAX_CONTEXT_TURNS | 200 | 문맥 턴 상한 (환경값 CONTEXT_TURNS의 안전 상한) |
| QUESTION_ABS_MAX_CHARS | 100_000 | 질문 길이 절대 상한 (DB CHECK 제약과 공유) |
| MAX_LOG_PAGE_SIZE | 200 | 로그 조회 페이지 상한 (DoS 방어) |
| MAX_AUDIT_REASON_CHARS | 200 | 관리자 열람 사유 최대 길이 |

### 4. 웹 보안 헤더 및 HTTP 인프라 규격 (Web Security & HTTP Infrastructure)
| 상수 | 값 | 역할 |
|---|---|---|
| CONTENT_SECURITY_POLICY | CSP 문자열 | 스크립트 실행/출처 제한 (인라인 차단) |
| SECURITY_HEADERS | 딕셔너리 | X-Content-Type-Options, HSTS 등 6종 보안 헤더 |
| DOCS_PATHS | 5종 경로 | 문서 경로 화이트리스트 (DOCS_ENABLED 가드 대상) |
| STATE_CHANGING_METHODS | 4종 메서드 | CSRF Origin 검증 대상 HTTP 메서드 |

### 5. 운영 기본값 상수 (Operational Defaults)
| 상수 | 값 | 역할 |
|---|---|---|
| DEFAULT_PAGE_SIZE | 50 | 목록 조회 기본 페이지 크기 (logs·threads·admin 공통) |
| RATE_WINDOW_SECONDS | 60.0 | 분당 요청 레이트 리미트 기본 윈도우 (초) |
| ADMIN_LOG_KEEP_ROWS | 5000 | 관리자 콘솔 이벤트·네트워크 로그 보존 한도 |

> **환경값으로 완화하지 않는 이유**: 운영자가 임의로 완화할 경우 서비스의 보안 경계(인라인 스크립트 허용, 비밀번호 잘림, DoS 공격 노출)가 훼손되는 것을 방지하기 위함입니다.

---

## ③′ 열거형 — 전수 (`app/enums.py`, 이벤트 이름은 `app/audit.E`)

| 열거형 | 멤버 | 공유 주체 |
|---|---|---|
| SessionKey | user_id / email_fp / iat | auth(기록) ↔ deps·미들웨어(판독) |
| ChatStatus | success / ai_error | DB 컬럼 기본값 ↔ API 응답 ↔ 성공 문맥 필터 |
| DeliveryResult | sent / dev_console | password_reset 서비스 ↔ auth 라우터 분기 |
| SchemaSyncStatus | pending / ok / error | database(기록) ↔ health(판독) |

StrEnum(str 상속)이라 기존 문자열 비교·DB 저장·JSON 직렬화와 호환된다.
