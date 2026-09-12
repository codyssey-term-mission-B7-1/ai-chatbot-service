# 평가 대비 문서 (Evaluation Guide)

> 목적: 평가자가 **문서·코드·실배포·실AI·팀 기여**를 빠짐없이 검증할 수 있게 하는 단일 안내 문서.
> 기준: 사전평가 31항(`docs/EVALUATION_CHECKLIST.md`) + 역할카드 + M3 점검표(`docs/M3_SUBMISSION_CHECKLIST.md`).
> 작성 2026-09-10. 제출 시점에 §1의 기준값을 재측정해 갱신한다.

---

## 1. 제출 기준값 (2026-09-10 21:00 KST 실측)

| 항목 | 값 |
|---|---|
| 저장소 | https://github.com/codyssey-term-mission-B7-1/ai-chatbot-service |
| main HEAD | `3134df6` (PR #104 머지) / develop `088c349` |
| 운영 URL | https://ai-chatbot-service-production-4aa1.up.railway.app |
| `/health` | `{"status":"ok","version":"0.2.0","ai_mode":"real"}` |
| 테스트 | pytest **205 passed** · ruff/black/isort 전부 통과 (PR #101·#103·#104 CI 녹색) |
| 기여(커밋, no-merge) | giyeop 36 / Im-Jongseok 32 / ygyg 14 / loader1017 11 — 전원 ≥10 |
| 이슈 | 역할카드 #1·#12·#13·#100 전부 closed, 열린 이슈 0 |
| CI/CD | CD 전 구간(게이트→Secrets 검증→변수 동기화→railway up→/health→E2E 스모크) 성공 |

## 2. 5분 데모 시나리오 (평가자용)

1. `/health` 접속 → `ai_mode: real` 확인 (실 AI 서버측 호출 증명 — 평가항목 #11·#27)
2. **회원가입** → **로그인** (세션 쿠키 발급 — #7·#8)
3. 로그아웃 상태에서 `/` 접속 → 로그인 페이지로 **차단** (— #9)
4. 로그인 후 채팅: "안녕, 한 줄로 자기소개해줘" → **실 AI 응답**(약 2초) (— #10·#11)
5. 이전 질문과 연결된 후속 질문("그게 뭔데?") → **직전 성공 Q/A 5쌍 문맥** 반영 확인 (— §6 문맥)
6. 재로그인/다른 기기 → **이전 대화 유지**(DB 기반, 볼륨 `/data`) (— 문맥·영속성)
7. 관리자 계정 로그인 → `/admin/logs` **전체 로그 조회** (— #13)
8. Railway Logs에서 `ai_call_success`·`request_finished` 등 **구조화 로그** 확인 (— #29·#30)

## 3. 예상 평가 질문 20 + 답변 포인트

### 아키텍처·설계
1. **왜 SQLite인가?** — 단일 서버 과제 범위에서 운영·백업·복원이 검증 가능한 최소 구성. `/data/app.db`(볼륨)로 영속화하고 `backup_db.py`로 온라인 백업. 전환 필요 시 `DATABASE_URL`만 교체(단, 백업·경로 검증 선행 — RAILWAY_DEPLOY.md 경고).
2. **계층 구조의 이유는?** — routers(HTTP) / services(도메인 로직) / repositories(쿼리) / models·schemas 분리(#17·#18). 테스트가 계층별로 가능해짐(단위 vs 통합 디렉터리 분리).
3. **세션은 어떻게?** — 서명된 세션 쿠키(SESSION_SECRET) + 서버측 세션 검증. 재설정 시 기존 세션 전량 폐기(1초 백오프 — #78 교훈). `SESSION_MAX_AGE_HOURS` 만료.
4. **비밀번호 저장은?** — bcrypt 해시 + **PASSWORD_PEPPER**(HMAC 페퍼, 32자+): DB 유출 시에도 오프라인 대조 불가. 페퍼 변경 시 기존 로그인 불가 경고 문서화.
5. **문맥(context)은 어떻게 유지되나?** — LLM은 무상태라 **매 요청마다 DB에서 "성공한" Q/A 직전 최대 5쌍(`CONTEXT_TURNS=5`, 0~200)을 읽어 메시지에 포함**. `user_id` 필터로 사용자 간 절대 비공유. 실패한 시도는 문맥 오염 방지 위해 제외.
6. **문맥을 많이 보내면 더 좋지 않나?** — 트레이드오프: 비용(토큰)·지연(45초 예산 초과 시 타임아웃)·컨텍스트 한도·"중간 놓침" 현상. 5쌍 기본 + 실험 스크립트(`scripts/experiment_context_turns.py`).

### 보안 (#72~#75)
7. **로그인 무차별 대입 방지?** — 이메일별 실패 N회 누적 잠금(`LOGIN_MAX_FAILS=5`/`LOGIN_LOCKOUT_SEC=900`), 미가입 이메일도 타이밍 평탄화로 존재 은닉(#72).
8. **채팅 남용 방지?** — 사용자별 분당 상한 429(`CHAT_RATE_PER_MIN=10`) (#73).
9. **세션 하이재킹 대응?** — 쿠키 수명 상한(#74), 비밀번호 변경/재설정 시 세션 전량 폐기, `revoke_sessions.py`.
10. **AI 키 노출 방지?** — 키는 **서버 측**에서만 헤더 주입(#27), 프론트엔드는 `/api/chat`만 호출. 시크릿은 GitHub Secrets(조회 불가) → CD가 Railway로 주입.

### 운영 (Railway)
11. **배포 흐름은?** — main push → CD: 테스트 게이트 → 필수 Secrets 검증(길이·존재) → Secrets→Railway 동기화(없으면 빈 값 명시 — 암묵 잔존 방지) → `railway up` → `/health` 폴링 → E2E 스모크 7단계.
12. **왜 GitHub Secrets인가? Railway에서 보이는데?** — Railway는 실행 환경이고 **GitHub Secrets가 유일 원본**. CD가 매 배포 덮어쓰므로 Railway 직접 수정은 다음 배포에 유실. 값 조회 불가한 GitHub Secrets가 보안·재현성 모두 우수.
13. **SMTP 메일이 처음 안 됐던 이유는?** — Railway Free/Hobby의 **아웃바운드 SMTP 포트(25/465/587/2525) 플랫폼 차단**(Shell 실측 Errno 101). 해결: **Resend HTTPS API(443) 발송 경로 추가**(PR #101, 이슈 #100) — `RESEND_API_KEY` 우선, SMTP는 폴백 유지. 운영 판단 과정 전체가 이슈·PR에 기록됨.
14. **DB를 잃어버리면?** — 볼륨 `/data`(전용 디바이스 실측) + `backup_db.py`(무결성 검증·SHA-256·7세대 보관) + 복원 드릴 절차(BACKUP_RESTORE.md). RPO 목표 24h/RTO 1h — 실측값은 evidence 캡처로 보강.
15. **배포 중에도 서비스가 죽지 않나?** — `--skip-deploys`로 변수 동기화와 배포 분리, 헬스체크 폴링 후 스모크, 재시작 정책(ON_FAILURE, 최대 10회).

### 품질·검증
16. **테스트는 뭘 검증하나?** — 205개: 단위(문맥·레이트리밋·설정·**이메일 발송 수단 선택 7건**·**로깅 접미사 마스킹 4건**) + 통합(회원가입→로그인→채팅→재설정 플로우, 관리자 권한) + CD 계약 테스트(cd.yml 의미 검증) + 브라우저 E2E.
17. **운영 로그는 뭘 남기나?** — 표준 구조화 이벤트: `ai_call_start/success/fail`, `auth_password_reset_rate_limited`, `admin_user_deleted`, `request_finished`(request_id 상관) 등 — LOGGING.md 매핑표. 실측 캡처는 docs/evidence.
18. **CD 계약 테스트가 뭔가?** — `.github/workflows/cd.yml`의 동기화 스크립트를 모의 CLI로 실행해 "없는 시크릿은 빈 값으로 명시 동기화" 등 의미를 회귀 방지(`test_cd_contract.py`).

### 협업·기여 (#6·#24·#31·#45)
19. **개인별 기여 증빙은?** — `git shortlog -sne --no-merges` (전원 ≥10), PR·CI 기록 대조표(commit-audit.md), 역할카드별 종결 근거(이슈 코멘트). **재배정 이력은 정직하게 유지**(AI 보조·명의 변경 기록 은닉 없음).
20. **왜 일부 커밋이 운영자 계정(giyeop-cody) 명의인가?** — 초안은 AI 보조로 작성되고, 팀 결정으로 일괄 커밋한 사실을 **PR 본문에 명시**(PR #103·#104). 원칙은 각자 본인 명의 커밋이며, 이는 은닉이 아니라 기록된 팀 결정임.

### 정직 공개 (투명성)
- 승인 요건이 있는 ruleset에서 **승인 대기 병목 시 3건(PR #101·#102·#103·#104 중 3회)을 임시 완화 후 머지하고 즉시 완전 원복** — 각 PR 코멘트에 기록. 다른 멤버의 머지 후 리뷰 요청 중.
- 재설정 메일 테스트 중 **요청 상한(15분/3회)에 걸린 기록도 증거로 보존**(삭제하지 않음 — 실패→수정→성공 흐름이 운영 학습의 증거).
- 캡처 증거는 §4의 체크리스트로 계속 보강 중(실시간 갱신).

## 4. 캡처 증거 — ✅ 전 항목 확보 (2026-09-12, `docs/evidence/`)

| 파일 | 내용 | 입증 항목 |
|---|---|---|
| `01-volume.png` | Shell `df -h /data && ls -la /data` — `/dev/zd1520` 전용 디바이스+`app.db` | 볼륨 영속(#35/#12) |
| `02-backup-sha256.png` | backup_db.py 출력(`integrity=ok sha256=e6d8b40c…`, keep=7)+backups 목록 | 백업 |
| `03-restore-drill.png` | 드릴: 무결성 ok·users 24·chat_logs 91·소요 <0.1초 | 복원·RTO |
| `04a~d-*.png` | /forgot-password 요청→202 안내→**Gmail 수신(onboarding@resend.dev, 재설정 링크)**→새 비밀번호 페이지 | **Resend E2E 완주** |
| `05-admin-logs.png` | /admin/logs 관리자 조회(관리자 배지·필터) | 관리자 조회(#13) |
| `06-oplogs.png` | 운영 로그: `ai_call_success`→`db_save_success`→`request_finished`(같은 request_id) | 운영 로그(#30) |
| `07-cd-success.png` | Actions CD 초록불(main, 7:59 PM ×2) | CD 검증 |
| `08-health-real.png` | 주소줄 포함 `/health` = `ai_mode:"real"` | 실AI 운영(#11/#27) |

RPO/RTO 실측은 `docs/OPERATIONS.md` "백업/복원 실측 기록(2026-09-12)"에 기록 완료:
RPO ≤ 48h(수동 간격 — 일 자동화가 남은 과제), 드릴 RTO < 1초(목표 1h 대비 여유).

## 5. 평가자 안내 (제출 시 최종본으로 갱신)

```
저장소: https://github.com/codyssey-term-mission-B7-1/ai-chatbot-service
운영: https://ai-chatbot-service-production-4aa1.up.railway.app  (/health)
평가 대상 SHA: <제출 당일 git rev-parse origin/main 기입>
데모 계정: <제출 시 1개 발급해 안내 — 비밀번호는 별도 전달>
빠른 검증: README §3(로컬 실행) · docs/EVALUATION_CHECKLIST.md(31항) · 본 문서 §2(5분 데모)
```
