# API 계약 — 현재 구현 기준

기본 URL은 실제 서버 주소다. 로컬 예시는 `http://localhost:8000`이며 운영에서는 HTTPS를 사용한다. `/docs`, `/redoc`, `/openapi.json`에서 현재 스키마를 볼 수 있다.

## 공통

- 인증: `POST /api/auth/login`이 발급한 **서명 세션 쿠키**를 보낸다. JWT가 아니다.
- Cookie payload는 `user_id`/`email_fp`; 값은 증빙에 복사하지 않는다. HttpOnly·SameSite=Lax·7일 Max-Age, 운영 Secure.
- 응답의 `X-Request-ID`는 앱 표준 이벤트·저장된 대화와 연결된다.
- 질문·비밀번호 문자 수는 Unicode 코드 포인트 기준. 비밀번호는 UTF-8 72바이트 제한도 적용한다.
- 모든 시각 응답은 UTC `Z` 형식이다. SQLite가 tzinfo를 보존하지 않아도 UTC 계약을 적용해 직렬화한다.

## 경로

| 메서드 | 경로 | 접근 / 성공 |
|---|---|---|
| POST | /api/auth/signup | 공개 / 201 |
| POST | /api/auth/login | 공개 / 200 + 쿠키 |
| POST | /api/auth/logout | 비로그인도 가능 / 200 |
| GET | /api/auth/me | 로그인 / 200 |
| POST | /api/chat | 로그인 / 200 |
| GET | /api/me/chats | 로그인 / 본인 기록 |
| GET | /api/admin/chats | 명시적 앱 관리자 / 전체 조회 |
| GET | /health | 공개 / 200 |

HTML `/`, `/logs`, `/admin/logs`는 비로그인일 때 `/login`으로 302 이동한다. 관리자가 아닌 로그인 사용자의 `/admin/logs`는 403이다.

## 회원가입

```http
POST /api/auth/signup
Content-Type: application/json

{"email":"hong@example.com","password":"Password123!","nickname":"홍길동"}
```
```json
{"email":"hong@example.com","nickname":"홍길동","is_admin":false}
```

- 이메일은 앞뒤 공백 제거·소문자 정규화, 중복은 409(동시 중복도 처리).
- 비밀번호는 8~64 코드 포인트 및 UTF-8 72바이트 이하. 한글 25자(75바이트)는 422다. 잘라 저장하지 않는다.
- 닉네임 최대 20자. 생략하면 이메일 접두어 앞 20자를 사용한다.
- 관리자 플래그 등 허용하지 않는 가입 필드는 422. 가입으로 권한이 생기지 않는다.

## 로그인 / 내 정보 / 로그아웃

```http
POST /api/auth/login
Content-Type: application/json

{"email":"hong@example.com","password":"Password123!"}
```
```json
{"email":"hong@example.com","nickname":"홍길동","is_admin":false}
```

성공 응답에는 `Set-Cookie: session=<마스킹>; ...`가 있다. 이메일/비밀번호 불일치는 동일한 401 메시지다. 미가입 이메일에도 같은 bcrypt 연산을 수행해 타이밍으로 존재 여부를 알 수 없게 한다.

같은 이메일의 실패가 `LOGIN_MAX_FAILS`회(기본 5) 이상 누적되면 `LOGIN_LOCKOUT_SEC`초(기본 900) 동안 429 + `Retry-After`로 잠긴다. 잠금 중에는 올바른 비밀번호도 거부되며 로그인 성공 시 카운터가 초기화된다.

`GET /api/auth/me`도 위 계정 정보를 반환한다. `POST /api/auth/logout`은 `{"detail":"로그아웃했어요."}`를 반환하며 현재 클라이언트 쿠키를 비운다. 복사된 쿠키를 중앙 세션 목록에서 개별 폐기하는 기능은 아니다.

## 채팅

```http
POST /api/chat
Content-Type: application/json
Cookie: session=<실제 요청에서만 사용, 증빙에서는 마스킹>

{"question":"내가 방금 뭘 물어봤지?"}
```
```json
{"answer":"직전에 배포 방법을 물어보셨어요.","latency_ms":1240,"chat_id":987,"status":"success"}
```

순서: 입력 검증 → 본인 성공 Q/A 최대 N쌍 → AI 호출 → DB 저장 시도 → HTTP 응답.

- `MAX_QUESTION_LENGTH` 기본 1000, 앞뒤 공백 제거 후 코드 포인트 수 검사. 프론트도 서버 설정값을 사용한다.
- `CONTEXT_TURNS` 0~200, 0이면 과거 문맥 없음. 성공 Q/A만 선택한다.
- `AI_TIMEOUT_SEC`는 AI 논리 호출 전체 예산이며 재시도/대기를 포함한다. DB·전체 HTTP 시간은 제외.
- Timeout은 504/AI_TIMEOUT. 형식 오류·기타 AI 실패는 502/AI_ERROR.
- 전송 오류·429·5xx만 최대 `AI_MAX_RETRIES` 추가 시도. 다른 4xx·형식 오류·타임아웃은 재시도하지 않는다.
- 키 없음 → Fake 데모 선택. 실 AI 실패를 Fake 성공으로 바꾸는 폴백은 없다.
- `status=success`는 AI 응답 성공만 의미한다. DB 실패는 `chat_id=-1`이며 기록이 남지 않을 수 있다.

사용자별로 `CHAT_RATE_PER_MIN`회(기본 10)/분을 초과하면 429 + `Retry-After`로 거부되며 이때 AI 호출·DB 저장은 일어나지 않는다. `CHAT_RATE_PER_MIN=0`이면 제한이 비활성화된다.

## 본인 기록

`GET /api/me/chats?limit=50&status=success&before_id=100`

```json
[{"id":99,"question":"이전 질문","answer":"이전 응답","latency_ms":1200,
  "status":"success","request_id":"example","created_at":"2026-09-08T00:00:00Z"}]
```

- 다른 사용자의 기록은 반환하지 않는다. 관리자가 이 경로를 호출해도 본인 기록만 반환한다.
- `status`: 생략 / `success` / `ai_error`. 필터를 적용한 **뒤** limit을 적용한다.
- limit은 1~200으로 제한(음수·0은 1). 최신 ID 순. `before_id`는 양수의 이전 페이지 커서.
- UI 복원은 `status=success&limit=N`을 요청하고 뒤집어 오래된 순으로 표시한다.

## 관리자 기록

`GET /api/admin/chats?limit=50&user_id=12&status=success&before_id=100`

```json
{"items":[{"id":99,"user_id":12,"question":"이전 질문","answer":"이전 응답",
  "latency_ms":1200,"status":"success","request_id":"example","created_at":"2026-09-08T00:00:00Z"}],
 "next_before_id":null}
```

명시적 관리자 grant가 필요하다. 비로그인 401, 비관리자 403. `user_id` 생략 시 전체 사용자를 대상으로 한다. 기본 관리자·공개 데모 관리자·클라이언트 자기 승격은 없다. [관리자 운영](ADMIN.md)

## 헬스체크

```json
{"status":"ok","version":"0.2.0","ai_mode":"demo"}
```

`ai_mode=real`은 키가 있어 실 제공자가 선택됐다는 뜻이지, 외부 AI 접속 성공 증거가 아니다.

## 오류 표

| 상태 | 의미 | 응답 |
|---|---|---|
| 401 | 로그인 필요 / 인증 실패 | `detail` 한국어 안내 |
| 403 | 앱 관리자 권한 없음 | `detail` 한국어 안내 |
| 409 | 이메일 중복 | `detail` 한국어 안내 |
| 429 | rate limit(로그인 잠금 등) | `detail` 한국어 안내 + `Retry-After` 헤더 |
| 422 | JSON/필드 검증 실패 | `detail` 배열, loc/type/msg/필요 ctx. 입력 원문은 제외 |
| 502 | AI 호출·응답 형식 오류 | `detail`에 AI_ERROR |
| 504 | AI 전체 예산/I/O 타임아웃 | `detail`에 AI_TIMEOUT |
| 500 | 예상하지 못한 내부 오류 | 일반화된 INTERNAL 안내 + 보안 헤더 + 요청 ID |

위 JSON은 설명용 예시다. 실제 실행 증거는 [검증 기록](VERIFICATION.md)의 환경·시각·소스 해시와 함께 확인한다.
