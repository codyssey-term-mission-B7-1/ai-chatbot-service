# API 명세서

기본 URL: `https://<서버호스트>` (로컬: `http://localhost:8000`)

**대화형 문서 (Swagger UI)**: `/docs` · **ReDoc**: `/redoc` · **OpenAPI JSON**: `/openapi.json`

인증 방식: **세션 쿠키** — `POST /api/auth/login` 응답의 `Set-Cookie: session=...` 을 이후 요청에 함께 전송 (curl에서는 `-c cookies.txt` / `-b cookies.txt`)

---

## 엔드포인트 개요

| 메서드 | 경로 | 인증 | 설명 | 성공 |
|--------|------|:---:|------|------|
| POST | `/api/auth/signup` | ✕ | 회원가입 | 201 |
| POST | `/api/auth/login` | ✕ | 로그인 (세션 쿠키 발급) | 200 |
| POST | `/api/auth/logout` | ○ | 로그아웃 (세션 삭제) | 200 |
| GET | `/api/auth/me` | ○ | 내 정보 조회 | 200 |
| POST | `/api/chat` | ○ | 질문 → AI 응답 (핵심 파이프라인) | 200 |
| GET | `/api/me/chats` | ○ | 내 대화 로그 조회 | 200 |
| GET | `/health` | ✕ | 헬스체크 | 200 |

---

## 1. 회원가입 — `POST /api/auth/signup`

**요청**
```json
{ "email": "hong@example.com", "password": "password123", "nickname": "홍길동" }
```
- `email`: 이메일 형식 필수 · `password`: 8자 이상 64자 이하 · `nickname`: 선택(공백이면 이메일 접두어)

**응답 201**
```json
{ "email": "hong@example.com", "nickname": "홍길동" }
```

**오류**
| 코드 | 상황 | 응답 예 |
|------|------|---------|
| 409 | 이미 가입된 이메일 | `{"detail": "이미 가입된 이메일이에요."}` |
| 422 | 입력 검증 실패 | `{"detail": [{"loc": ["body","password"], "msg": "..."}]}` |

---

## 2. 로그인 — `POST /api/auth/login`

**요청**
```json
{ "email": "hong@example.com", "password": "password123" }
```

**응답 200** (헤더에 `Set-Cookie: session=...`)
```json
{ "email": "hong@example.com", "nickname": "홍길동" }
```

**오류** — 401: `{"detail": "이메일 또는 비밀번호가 올바르지 않아요."}` (계정 존재 여부 노출 안 함)

---

## 3. 채팅 (핵심 파이프라인) — `POST /api/chat`

처리 흐름: **질문 수신 → 직전 N개 Q/A 컨텍스트 구성 → AI API 호출 → 응답 반환 → DB 저장**

**요청**
```json
{ "question": "내가 방금 뭘 물어봤지?" }
```
- `question`: 필수, 공백만 있으면 불가, 최대 1000자

**응답 200**
```json
{
  "answer": "직전에 'FastAPI로 배포하는 방법 알려줘'를 물어보셨고, ...",
  "latency_ms": 1240,
  "chat_id": 987,
  "status": "success"
}
```

**오류**
| 코드 | 상황 | 응답 예 |
|------|------|---------|
| 401 | 비로그인 | `{"detail": "로그인이 필요한 기능이에요."}` |
| 422 | 빈 질문/1000자 초과 | Pydantic 검증 오류 |
| 502 | AI 호출 실패 | `{"detail": "AI 서버에 문제가 생겼어요. 잠시 후 다시 시도해 주세요. (error: AI_ERROR)"}` |
| 504 | AI 타임아웃 | `{"detail": "현재 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요. (error: AI_TIMEOUT)"}` |

> 타임아웃/실패 시에도 서버는 종료되지 않으며, 실패 이력은 `status=ai_error`로 DB에 기록되어 추적 가능합니다.

---

## 4. 내 대화 로그 조회 — `GET /api/me/chats?limit=50`

**응답 200**
```json
[
  {
    "id": 987,
    "question": "내가 방금 뭘 물어봤지?",
    "answer": "직전에 'FastAPI로 배포하는 방법...' 를 물어보셨고, ...",
    "latency_ms": 1240,
    "status": "success",
    "created_at": "2026-09-01T10:30:00Z"
  }
]
```
- 본인 로그만 반환 (다른 사용자 로그 접근 불가) · `limit` 최대 200 · 최신순 정렬

---

## 5. 로그아웃 / 내 정보 / 헬스체크

```bash
curl -X POST -b cookies.txt https://SERVER/api/auth/logout
# → {"detail": "로그아웃했어요."}

curl -b cookies.txt https://SERVER/api/auth/me
# → {"email": "hong@example.com", "nickname": "홍길동"}

curl https://SERVER/health
# → {"status": "ok", "ai_mode": "demo"}   (ai_mode: real|demo)
```

---

## 전체 시나리오 (curl 복사용)

```bash
BASE=http://localhost:8000
EMAIL=me@example.com

# ① 회원가입 + 로그인
curl -X POST $BASE/api/auth/signup -H 'Content-Type: application/json' \
     -d "{\"email\":\"$EMAIL\",\"password\":\"password123\"}"
curl -c cj.txt -X POST $BASE/api/auth/login -H 'Content-Type: application/json' \
     -d "{\"email\":\"$EMAIL\",\"password\":\"password123\"}"

# ② 대화 (문맥 형성)
curl -b cj.txt -X POST $BASE/api/chat -H 'Content-Type: application/json' \
     -d '{"question": "FastAPI 배포 방법 알려줘"}'

# ③ 문맥 확인 — 직전 질문을 인용하는지
curl -b cj.txt -X POST $BASE/api/chat -H 'Content-Type: application/json' \
     -d '{"question": "내가 방금 뭘 물어봤지?"}'

# ④ 내 로그 조회
curl -b cj.txt "$BASE/api/me/chats"
```

## 오류 코드 요약

| 코드 | 에러명 | 의미 | 사용자 안내 |
|------|--------|------|-------------|
| 401 | — | 인증 필요/실패 | 로그인 안내 |
| 409 | — | 이메일 중복 | 중복 안내 |
| 422 | — | 입력 검증 실패 | 필드별 안내 |
| 502 | `AI_ERROR` | AI API 호출 실패 | 잠시 후 재시도 안내 |
| 504 | `AI_TIMEOUT` | AI 타임아웃 초과 | 지연 안내 + 재시도 |
| 500 | `INTERNAL` | 미처리 서버 오류 | 일괄 안내 (서버 생존) |
