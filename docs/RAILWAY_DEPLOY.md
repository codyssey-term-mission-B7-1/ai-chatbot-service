# Railway 배포 런북

## 현재 상태

2026-09-09 첫 운영 배포에 성공했다. CD 전 구간(게이트 → Secrets 검증 → 변수 동기화 → `railway up` → `/health` → E2E 스모크 7/7)이 통과했으며 [실행 기록](https://github.com/codyssey-term-mission-B7-1/ai-chatbot-service/actions/runs/34324577000)에서 확인한다.

- 운영 URL: https://ai-chatbot-service-production-4aa1.up.railway.app (저장소 homepage 등록됨)
- 현재 `ai_mode=demo` — `AI_API_KEY` Secret 등록 후 재배포 시 실 AI로 전환 (절차는 [OPERATIONS.md](OPERATIONS.md) P0-1)

**이 문서 자체는 배포 성공 증거가 아니다.** 이후 배포도 매번 CD 기록·헬스·E2E 성공을 확보해야 한다.

## 운영자가 준비할 것

1. Railway 프로젝트의 서비스와 영구 Volume을 생성하고 `/data`에 마운트한다.
2. 서비스를 공개 HTTPS 도메인으로 노출한다.
3. Railway **프로젝트 토큰**을 발급한다. GitHub PAT나 AI 키로 대신하지 않는다.
4. GitHub Actions Secrets에 필수 값을 등록한다.

| Secret | 필수 | 의미 |
|---|---|---|
| RAILWAY_TOKEN | 예 | Railway 프로젝트 토큰 |
| DEPLOY_URL | 예 | 실제 HTTPS 서비스 URL, 끝 `/` 없음 |
| SESSION_SECRET | 예 | 새 무작위 32자 이상 값. 코드/대화/증빙에 공개하지 않음 |
| AI_API_KEY | 선택 | 실제 AI 키. 없으면 **빈 값으로 동기화**하여 데모 모드 |
| AI_BASE_URL | 선택 | 기본 `https://api.openai.com/v1/chat/completions` |
| AI_MODEL | 선택 | 기본 `gpt-4o-mini` |
| AI_TIMEOUT_SEC | 선택 | 기본 45초, AI 전체 호출 예산 |
| AI_MAX_RETRIES | 선택 | 기본 1, 추가 시도 0~5 |
| CONTEXT_TURNS | 선택 | 기본 5, 0~200 |
| CHAT_RATE_PER_MIN | 선택 | 기본 10. 사용자별 분당 채팅 상한, 0=비활성 (#73) |
| LOGIN_MAX_FAILS | 선택 | 기본 5. 이메일별 로그인 실패 잠금 기준 (#72) |
| LOGIN_LOCKOUT_SEC | 선택 | 기본 900. 로그인 잠금 지속 초 (#72) |
| SESSION_MAX_AGE_HOURS | 선택 | 기본 24. 세션 쿠키 수명 시간 (#74) |
| DOCS_ENABLED | 선택 | 기본 false. /docs·/redoc·/openapi.json 노출 (#75) |
| MAX_QUESTION_LENGTH | 선택 | 기본 1000 코드 포인트 |
| DATABASE_URL | 선택 | 기본 `sqlite:////data/app.db` |
| SMTP_HOST/PORT/USER/PASSWORD/FROM | 선택 | SMTP 메일 발송. 없으면 빈 값 동기화(운영 503). **Railway Free/Hobby는 SMTP 아웃바운드(25/465/587/2525) 차단 — Pro가 아니면 발송 불가** |
| RESEND_API_KEY | 선택 | HTTPS 이메일 발송(Resend, 443포트). Railway Free/Hobby의 SMTP 차단 우회용. **설정 시 SMTP보다 우선** |
| RESEND_FROM | 선택 | 기본 `onboarding@resend.dev`. 도메인 인증 전엔 수신이 Resend 계정 본인 이메일로 제한 |

Variables: `RAILWAY_SERVICE_NAME` 기본 ai-chatbot-service, `RAILWAY_ENVIRONMENT` 기본 production.

## 동기화 계약과 주의

- 관리 대상 변수의 미설정은 **기본값/빈 값 적용**이다. 이전 Railway 값을 유지하는 동작이 아니다.
- 특히 AI_API_KEY Secret을 제거하면 대상 값도 비운다. 실 AI를 계속 써야 한다면 값을 빠뜨리지 말아야 한다.
- 운영 DEBUG는 **false로 고정**한다. DEBUG Secret을 추가해도 true로 동기화하지 않는다.
- 대상 서비스/환경과 기존 값을 운영자가 확인한 뒤 실행한다. 실제 Secret 값은 로그/커밋에 넣지 않는다.
- `DATABASE_URL`을 바꾸면 다른 DB를 사용할 수 있으므로 먼저 백업과 영구 볼륨 경로를 검증한다.
- `.env` 변경/환경변수 동기화 후에는 새 앱 프로세스가 필요하다. `reset_provider`만 호출해도 환경변수가 다시 읽히는 것은 아니다.
- **스키마는 앱 시작 시 자동 동기화**(`init_db` → alembic). 스키마 변경 배포 후 `/health.build`가 새 SHA로 바뀌어도 **스키마까지 된 보장이 아니다** — `init_db` 실패는 프로세스 기동을 막지 않고 로그에만 남는다(2026-09-13 운영 사고: alembic 도입 전 만들어진 운영 DB에 `alembic_version`이 없어 마이그레이션이 조용히 실패, 신규 스키마 API 500). 이제 `init_db`는 버전 테이블이 없는 레거시 DB를 자동으로 인수(adopt)한다(최신 스키마면 head 스탬프, 아니면 base 리비전 스탬프 후 누락 마이그레이션). 스키마 변경 배포 후엔 해당 스키마를 쓰는 API 하나를 실제 호출해 확인한다.

## 실행

기존 `.github/workflows/cd.yml`은 main push 및 workflow_dispatch에서 동작한다.

**시작 명령은 루트의 `Procfile`이 제공한다.** Railway의 신규 빌더(Railpack)는 deprecated된 `railway.json`의 `startCommand`를 무시하고 자동 감지를 시도하며, `app/main.py` 구조는 감지 규칙에 없어 빌드가 실패한다(2026-09-09 실측). `Procfile`은 Nixpacks/Railpack 공통으로 인식되므로 저장소에서 시작 명령을 계속 관리한다. `railway.json`은 헬스체크/재시작 정책의 의도 문서로 유지한다.

1. ruff·pytest 게이트
2. 프론트 JS 난독화(`tools/js-build`, in-place — 배포 산출물만, ADR-009)
3. 필수 Secrets 검증 — 실패하면 배포하지 않는다
4. Railway 변수 동기화(`--skip-deploys`) — `BUILD_SHA`(=커밋 SHA, Secret 아님)도 포함
5. `railway up`
6. 새 배포 롤아웃 대기 — `/health.build`가 이번 커밋과 일치할 때까지 최대 10분
   (health·스모크가 구버전 인스턴스에 통과하는 눈먼 구간 제거, #120)
7. E2E 스모크
8. JS 난독화 배포 검증(로컬 결정적 산출물과 바이트 일치, 최대 10분 + 문법)

단순 `/health`의 ai_mode=real은 외부 AI 접속 성공을 뜻하지 않는다. 실 AI는 `ai_check.py --require-real`로 별도 검증한다.

## 영속화·운영 증빙

- 가입/로그인 후 고유한 시험 질문을 저장한다.
- 재배포 후 같은 계정의 `/api/me/chats`에서 해당 질문이 남아 있는지 확인한다.
- `SESSION_SECRET`을 바꾸면 다시 로그인해야 한다. DB의 사용자 ID와 세션 지문이 다르면 오래된 세션은 거부된다.
- 백업은 `python scripts/backup_db.py /data/app.db`를 사용한다. 기본 출력은 `/data/backups/`다.
- 운영 스케줄러·서버 밖 백업 보관·복원 드릴은 운영자가 실제로 수행하고 기록해야 한다.

[관리자 계정](ADMIN.md) · [백업/복원](BACKUP_RESTORE.md) · [검증 구분](VERIFICATION.md)

## 실패 시

필수 Secrets 실패는 해당 설정을 안전하게 등록한 뒤 다시 실행한다. 성공한 것처럼 로그를 교체하거나 실패 단계를 건너뛰지 않는다. 실제 URL이 없으면 README/homepage에 임의 주소를 쓰지 않는다.
