# Railway 배포 런북 (GitHub Actions CI/CD + DB 영속화)

> 관련 이슈: #12 (배포 & 운영) · 파이프라인: `.github/workflows/cd.yml`
> 원칙: 환경변수 source of truth = **GitHub Secrets**, DB는 **Volume**에 영속화 (재배포해도 초기화 안 됨)

## 1. 아키텍처

```
main 머지 ─▶ [gate] ruff+pytest ─▶ [sync] Secrets→Railway 변수 ─▶ [up] railway up
                                                              ─▶ [health] /health 폴링
                                                              ─▶ [smoke] e2e_smoke.sh
```

- 배포 단위: `railway.json` (Nixpacks 빌드, `$PORT` 수신, `/health` 헬스체크)
- DB: Railway Volume → `/data` 마운트 + `DATABASE_URL=sqlite:////data/app.db`
- 앱은 시작 시 테이블만 생성(`create_all` — 비파괴). 삭제·초기화 코드는 없음

## 2. 최초 1회 설정 (사람 작업, 약 10분)

### 2-1. Railway 프로젝트·서비스·볼륨

1. [railway.app](https://railway.app) → New Project → **Empty Service** (GitHub 연동 배포는 끔 — Actions가 배포)
2. 서비스 이름: `ai-chatbot-service` (다르면 Variables `RAILWAY_SERVICE_NAME`에 지정)
3. 서비스 → **Volumes** → Add Volume, 마운트 경로: `/data`
4. 서비스 → **Settings → Networking** → Generate Domain (공개 URL 확보 → `DEPLOY_URL`)
5. 프로젝트 → **Tokens** → Project Token 발급 (→ `RAILWAY_TOKEN`)

### 2-2. GitHub Secrets 등록 (Settings → Secrets and variables → Actions)

| Secret | 필수 | 값 예시 |
|---|---|---|
| `RAILWAY_TOKEN` | ✅ | Railway project token |
| `DEPLOY_URL` | ✅ | `https://xxx.up.railway.app` (끝 `/` 없음) |
| `SESSION_SECRET` | ✅ | 32자 이상 무작위 (`python -c "import secrets;print(secrets.token_hex(32))"`) |
| `AI_API_KEY` | 선택 | 네이토/OpenAI 키 (없으면 데모 모드) |
| `AI_BASE_URL` | 선택 | OpenAI 호환 엔드포인트 |
| `AI_MODEL` | 선택 | 모델명 |
| `AI_TIMEOUT_SEC` / `AI_MAX_RETRIES` / `CONTEXT_TURNS` | 선택 | 기본값 사용 시 생략 |
| `DATABASE_URL` | 선택 | 미설정 시 `sqlite:////data/app.db` 자동 적용 |

선택 Variables: `RAILWAY_SERVICE_NAME` (기본 `ai-chatbot-service`), `RAILWAY_ENVIRONMENT` (기본 `production`).

## 3. 배포 실행

- **자동**: `develop` → `main` PR 머지 시 CD 실행
- **수동**: Actions → CD → Run workflow (재배포·변수 재동기화)

실패 시 Actions 로그에서 단계별 확인 (게이트 → 검증 → 동기화 → up → 헬스 → 스모크 순).

## 4. DB 영속화 검증 (첫 배포 후 1회)

```bash
# 1) 배포본에 질문 1건 (쿠키 저장)
curl -c cj.txt -X POST $DEPLOY_URL/api/auth/signup \
  -H 'Content-Type: application/json' -d '{"email":"probe@test.com","password":"Test1234!"}'
curl -b cj.txt -c cj.txt -X POST $DEPLOY_URL/api/auth/login \
  -H 'Content-Type: application/json' -d '{"email":"probe@test.com","password":"Test1234!"}'
curl -b cj.txt -X POST $DEPLOY_URL/api/chat \
  -H 'Content-Type: application/json' -d '{"question":"영속화_probe"}'

# 2) 재배포 (Actions 수동 실행 또는 빈 커밋 main 머지)

# 3) 같은 계정으로 로그 조회 — probe 질문이 남아있으면 성공
curl -b cj.txt -c cj.txt -X POST $DEPLOY_URL/api/auth/login \
  -H 'Content-Type: application/json' -d '{"email":"probe@test.com","password":"Test1234!"}'
curl -b cj.txt $DEPLOY_URL/api/me/chats | grep -o "영속화_probe"
```

> 참고: 재배포 후 기존 세션 쿠키는 무효화될 수 있음 (위 절차처럼 재로그인).
> 세션 `max_age` 적용 전까지 probe 계정은 삭제하지 말 것.

## 5. 재배포·롤백·백업

- **재배포**: Actions 수동 실행 (DB 유지됨 — Volume이 살아있는 한)
- **롤백**: Railway 대시보드 → Deployments → 이전 버전 Redeploy (DB는 건드리지 않음)
- **백업**: `scripts/backup_db.sh` + 볼륨 파일 주기적 다운로드 (정책: `docs/BACKUP_RESTORE.md`)
- **주의**: Volume 삭제 = DB 영구 삭제. 볼륨 설정 변경 전 반드시 백업

## 6. 트러블슈팅

| 증상 | 원인 → 조치 |
|---|---|
| `unable to open database file` | 볼륨 미마운트 → `/data` 마운트 + `DATABASE_URL` 확인 |
| 배포마다 데이터 초기화 | Volume 없이 배포 중 → 2-1 절차 3번 확인 (ephemeral disk) |
| CD가 Secrets 검증에서 실패 | 필수 3종(RAILWAY_TOKEN·DEPLOY_URL·SESSION_SECRET) 등록 여부 확인 |
| 헬스체크 5분 실패 | 빌드 로그(railway.json startCommand·`$PORT`) 확인 |
| 데모 응답만 반환 | `AI_API_KEY` 미설정 → Secrets 등록 후 재배포 (변수만 바뀌면 Actions 수동 실행) |
| `railway` 명령어 오류 | CLI 버전 변경 가능 — `railway <cmd> --help`로 플래그 확인 후 `cd.yml` 수정 |

## 7. 보안 주의

- 시크릿 값은 Actions 로그에 자동 마스킹 — 그래도 `echo $SECRET` 금지 (워크플로는 유무·길이만 검사)
- `SESSION_SECRET` 교체 시 전원 로그아웃 (세션 서명 변경)
- `RAILWAY_TOKEN`은 프로젝트 풀권한 — 유출 시 즉시 재발급·폐기
