# 접근 제어 매트릭스 (Access Control Matrix)

> 경로 × 인증 상태별 동작 — 카드 05 증빙 문서 · 테스트로 자동 검증되는 항목은 ✅
> 최종 검증일: 2026-09-07 (테스트 38개 통과 기준)

| 경로 | 비로그인 | 로그인 | 자동 검증 |
|------|----------|--------|:---------:|
| `GET /` (채팅) | → `/login` 리다이렉트 (302) | 200 채팅 화면 | 수동 |
| `GET /logs` (내 기록) | → `/login` 리다이렉트 | 200 (본인 로그만) | 수동 |
| `GET /login`, `GET /signup` | 200 | → `/` 리다이렉트 (302) | 수동 |
| `POST /api/auth/signup` | 201 (계정 생성) | — | ✅ `test_signup_login_me_logout_flow` |
| `POST /api/auth/login` | 200 + 세션 쿠키 | 200 | ✅ 동일 |
| `POST /api/auth/logout` | 200 (세션 없어도 정상) | 200 + 세션 파기 | 수동 |
| `GET /api/auth/me` | **401** | 200 본인 정보 | ✅ `test_me_requires_login` |
| `POST /api/chat` | **401** | 200 AI 응답 | ✅ `test_chat_blocked_without_login` |
| `GET /api/me/chats` | **401** | 200 **본인 로그만** (타인 차단) | ✅ `test_my_chats_isolated_per_user` |
| (세션 끊김/소실 시) | 위 보호 API 전부 **401** | — | ✅ `test_session_loss_blocks_protected_api` |
| (stale 세션: DB 재생성 후 id 재할당) | 위 보호 API 전부 **401** + 세션 파기 | — | ✅ `test_stale_session_after_reseed_returns_401` |
| `GET /health` | 200 | 200 | ✅ E2E 스모크 ① |

## 설계 근거

- **세션 쿠키 방식**: 서버가 발급·서명(SigningMiddleware) → JS에서 토큰 관리 불필요, XSS로 쿠키 탈취 시 HttpOnly로 완화. 과제 규모에서 JWT 대비 구현·디버깅 단순
- **통일된 401 메시지**: "로그인이 필요한 기능이에요." — 프론트가 동일 로직으로 로그인 페이지 유도
- **데이터 격리**: 조회 쿼리가 항상 `user_id == 본인` 필터 → IDOR(타인 리소스 접근) 구조적 차단
- **세션-계정 바인딩**: 세션에 `user_id`+`email` 저장, 매 요청 대조 → 불일치면 파기+401 (DB 재생성 후 타계정 오인 방지 — #33)
- **로그인 실패 메시지 통일**: 계정 존재 여부 노출 안 함 (사용자 열거 공격 방지)

## 유지 보수 규칙

- 새 보호 라우트 추가 시 이 표에 행 추가 + 401 테스트 작성 (PR 체크리스트)
- 이 문서는 정적 문서라 코드와 어긋날 수 있음 → ✅ 열은 테스트 이름과 항상 함께 갱신
