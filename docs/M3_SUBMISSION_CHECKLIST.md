# M3 최종 제출 증빙 점검표

> 목적: 평가가 보는 **"문서 · Git · 코드 · 실배포 · 실AI"** 를 빠짐없이 연결하는 최종 제출 게이트.
> 상태 범례: `[x]` = 증거 확정 / `[ ]` = 외부 완료 필요 / `[~]` = 로컬 검증만 된 상태(운영 승격 필요)
> 초안 2026-09-09 → **실측 갱신 2026-09-10**. 제출 전 팀이 최종 수치로 재확인한다.
> 작성자별 커밋은 각 담당자가 직접 남긴다.

---

## 1. 제출 기준값 (2026-09-10 실측)
- [x] 기준 SHA — main `a6955f4`(Resend 전환 머지, PR #101) / develop `088c349`
- [~] `git shortlog -sne --no-merges origin/develop` (2026-09-09 실측):
      giyeop 36 / Im-Jongseok 32 / ygyg 14 / loader1017 11 — **전원 10커밋 이상 달성**.
      제출 당일 최신본으로 재측정해 첨부할 것
- [x] 실운영 `/health` = `{"status":"ok","version":"0.2.0","ai_mode":"real"}`
      (2026-09-10 17:41·19:37 CD 성공 후 실측, https://ai-chatbot-service-production-4aa1.up.railway.app)
- [x] 실 AI 동작 증명 — 운영에서 실제 AI 응답 확인(한국어 자기소개 응답, latency 1.6~2.0초, 2회 실측).
      `scripts/ai_check.py --require-real` 로컬 캡처는 선택(운영 real이 상위 증거)
- [x] pytest **221 passed**(2026-09-11, PR #107 병합 시점 전체 스위트 — 평가 대비 하드닝 테스트 5건 포함)
      / ruff·black·isort 전부 통과 (CI run: PR #107 ci·browser 녹색, CD run 34557356968 전 구간 성공)
      · 이전 실측: 205 passed(2026-09-10, PR #101 시점)

## 2. 사전평가 31항 연결표 (증거 위치)
> 각 행은 `docs/EVALUATION_CHECKLIST.md`와 1:1. 증거 기준 = 실제 소스 경로 + 테스트명 또는 캡처.

| # | 주제 | 증거 위치(소스·테스트·캡처) | 판정 |
|---|---|---|---|
| 1 | 문제·사용자·시나리오 | README §1 | [x] |
| 2 | 아키텍처·컴포넌트 책임 | README §2 · app/routers,app/services,app/repositories | [x] |
| 3 | API 요청·응답 예제 | docs/API.md · /openapi.json | [x] |
| 4 | DB 구조·ERD·제약 | README ERD · app/models.py | [x] |
| 5 | 사용자별 로그·SQL | app/routers/logs.py · scripts/check_logs.sql | [x] |
| 6 | 역할·개인별 기여 증빙 | README 역할표 · docs/commit-audit.md · shortlog 표(§1) | [x] |
| 7 | 회원가입 UI | templates/login.html · evidence 캡처 | [x] |
| 8 | 로그인·세션 발급 | app/routers/auth.py · app/deps.py · session 테스트 | [x] |
| 9 | 비로그인 접근 차단 | test_auth_flow.py · test_verified_gaps.py | [x] |
| 10 | 질문·응답 UI | templates/chat.html · evidence 캡처 | [x] |
| 11 | 서버→AI 호출 | app/services/ai_client.py · **운영 real 모드 실측**(§1) | [x] |
| 12 | 질문·응답 DB 저장 | app/repositories/chat_logs.py · test_chat_flow.py | [x] |
| 13 | 관리자 전체 조회 | app/routers/admin.py · test_admin.py · **docs/evidence/05-admin-logs.png** | [x] |
| 14 | 타임아웃·예외·생존 | test_ai_http_budget.py | [x] |
| 15 | 오류 코드·안내 | docs/API.md · form-utils.js | [x] |
| 16 | 입력 검증 | app/schemas.py · test_schema_edge_cases.py | [x] |
| 17 | 라우터·서비스·모델·스키마 분리 | app/ 구조 | [x] |
| 18 | 목적별 라우트 분리 | routers/auth·chat·logs·admin·pages | [x] |
| 19 | Pydantic 실제 사용 | app/schemas.py · response_model | [x] |
| 20 | 인증 DI·미들웨어 | app/deps.py · SessionMiddleware | [x] |
| 21 | 모델·세션·CRUD 계층 | app/models.py · repositories | [x] |
| 22 | 민감정보 제외 | .gitignore · 시크릿은 GitHub Secrets(값 비공개)만 | [x] |
| 23 | .env.example | .env.example(RESEND_* 포함) · README 실행법 | [x] |
| 24 | PR·병합 증빙 | PR #101(이슈 #100 자동종료)·CI 기록 외 전원 PR | [x] |
| 25 | 실제 REST 엔드포인트 | docs/API.md · OpenAPI 자동검증 | [x] |
| 26 | 로그인 제한 근거 | docs/ACCESS_CONTROL.md | [x] |
| 27 | AI 키 서버측 사용 | app/services/ai_client.py 헤더 · 운영 real 실측 | [x] |
| 28 | 재시도·대체 정책 | docs/API.md · test_ai_policies.py | [x] |
| 29 | 로그 목적 매핑 | docs/LOGGING.md | [x] |
| 30 | 실제 운영 로그 증빙 | **docs/evidence/06-oplogs.png**(`ai_call_success`→`db_save_success`→`request_finished` 동일 request_id) · `rate_limited` 트레이스 · `admin_user_deleted` | [x] |
| 31 | 문서·Git·PR 대조 | commit-audit + shortlog + PR 대조표 | [x] |

## 3. 이슈 종결 근거 (2026-09-10 기준 열린 이슈 3개)
> 초기 10개 이슈는 모두 종결됨(2026-09-09~10). 마지막 추가 종결: #100 Railway Free/Hobby
> SMTP 차단 → Resend HTTPS 전환(PR #101, merge `a6955f4`).

| 이슈 | 종결 근거(증거) | 담당 |
|---|---|---|
| #1 총괄/PM | 회고 문서(docs/retro/M1.md PR) + 마일스톤 근거 + 이슈 조율 기록 | giyeop |
| #12 배포&운영 | CD 성공 기록(최신 2026-09-10 10:37Z) + /health real + 볼륨/백업 확인 + 관리자 부트스트랩 + 테스트계정 23건 정리(audit 로그) + RESEND_API_KEY 등록 | ygyg |
| #13 문서&검증 | 본 점검표(이 PR) + 운영 로그 캡처 패키지 + loader 로깅 회귀테스트 PR | ygyg/loader |

## 4. 제출 전 최종 런북 — 달성 상황
1. [x] 실 AI: GitHub Secrets(AI_API_KEY/BASE_URL/MODEL) → CD → **real** 확인(2026-09-10 17:41)
2. [x] 이메일: Railway SMTP 차단 확인(Errno 101) → **Resend HTTPS 전환**(PR #101) → RESEND_API_KEY 등록 → 재배포(10:37Z)
       → 재설정 메일 **발송→수신 완주**(2026-09-12, Gmail 수신 — `docs/evidence/04a~d` 4컷)
3. [x] 운영 로그: `docs/evidence/06-oplogs.png` 확보(#30 행)
4. [x] 백업: 볼륨 `/data` 실측(`01-volume.png`) + 백업 SHA-256(`02`) + 복원 드릴(`03`, 무결성 ok·<0.1초) + **RPO≤48h/RTO<1초 OPERATIONS.md 기록 완료** — RPO 24h 목표 자동화는 남은 과제
5. [x] 기여: loader 11커밋(≥10) — shortlog 표 §1
6. [x] 문서: commit-audit 재배정 이력 정직 유지 + 본 점검표 갱신(이 PR)
7. [ ] 평가자 접근용: 최종 main SHA·URL·데모 계정 안내 문구 — 제출 당일 마지막 작업
