# 운영 체크리스트 — 사용자 발급이 필요한 P0와 자가 진단 방법

이 문서는 **코드 배포가 끝난 뒤 운영자가 직접 해야 하는 일**의 절차서다.
모든 항목은 "발급 → GitHub Secrets 등록 → 검증" 3단계로 구성된다.

라이브 URL: https://ai-chatbot-service-production-4aa1.up.railway.app

---

## P0-1. AI_API_KEY (실제 AI 응답 활성화)

**현재 상태**: 미등록 → 데모(Fake) 모드로만 응답 (`ai_mode=demo`).

### 발급 (아무거나 하나 — OpenAI 호환이면 전부 가능)
| 제공자 | 콘솔 | 비고 |
|---|---|---|
| OpenAI | platform.openai.com → API keys | `AI_MODEL=gpt-4o-mini` 기본값 그대로 사용 |
| Groq | console.groq.com → API Keys | 무료 쿼터 큼. `AI_MODEL`은 문서에서 확인 |
| 코디세이 '네이토' | 코디세이 콘솔 → API 문서 | `AI_BASE_URL`과 `AI_MODEL`을 문서 값으로 변경 |

### 등록
1. GitHub 레포 → **Settings → Secrets and variables → Actions → New repository secret**
2. `AI_API_KEY` = (발급한 키). 코디세이 사용 시 `AI_BASE_URL`·`AI_MODEL`도 추가
3. 다음 main 병합 시 CD가 자동으로 Railway 변수에 동기화한다 (즉시 적용을 원하면
   Actions → CD → Run workflow로 수동 실행)

### 검증
- 라이브에서 실제 질문 → 데모 문구가 아닌 실제 답변이 오는지 확인
- 서버 로그에 `event=ai_call_success` 기록 (Railway → Deployments → Logs)

---

## P0-2. SMTP 자격증명 (비밀번호 재설정 메일)

**현재 상태**: 미등록 → 가입된 이메일로 재설정 요청 시 503 ("메일 발송 설정이 되어 있지 않아…").

### 발급 (Gmail 예시 — 2단계 인증 필수)
1. Google 계정 → 보안 → **2단계 인증 사용 설정** (이미 있으면 통과)
2. Google 계정 → 보안 → 앱 비밀번호 검색 → **새 앱 비밀번호 생성**
   (16자리 비밀번호 발급 — `앱 비밀번호`는 2단계 인증이 있어야만 메뉴가 보인다)

### 등록 (GitHub Secrets 5종)
| Secret | 값 |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` (SSL) 또는 `587` (STARTTLS) |
| `SMTP_USER` | Gmail 주소 |
| `SMTP_PASSWORD` | 발급받은 16자리 앱 비밀번호 (공백 제거) |
| `SMTP_FROM` | `AI Chatbot Service <본인@gmail.com>` |

> 대안: SendGrid/Mailgun/SMTP를 제공하는 어떤 서비스든 무방하다. 465=SSL, 587=STARTTLS 자동 감지.

### 검증
1. 라이브 → 로그인 → "비밀번호 찾기" → 본인 이메일 입력
2. 메일함에 재설정 링크 수신 확인 (스팸함 포함)
3. 링크 → 새 비밀번호 설정 → 새 비밀번호로 로그인

---

## P0-3. 관리자 계정 (부트스트랩)

권한은 **DB의 `admin_grants` 테이블**로 관리된다 — 회원가입만으로는 절대 권한을 얻을 수 없고,
**서버 CLI(`scripts/manage_admin.py`)로만 부여** 가능하다 (설계 의도).

### 절차
1. **관리자 전용 계정 회원가입**: 라이브에서 본인 이메일로 일반 회원가입
   (기존 개인 이메일을 써도 무방 — 데모 계정은 거부됨)
2. **서버 CLI 실행** (둘 중 하나):
   - **Railway 웹 셸**: Railway 대시보드 → ai-chatbot-service → 최신 배포 → **Shell** 탭 →
     아래 명령 실행
   - **Railway CLI**: `railway ssh --service ai-chatbot-service` 후 아래 명령 실행
     (개인 계정 로그인 필요 — 프로젝트 토큰으로는 SSH 키 등록 불가, 2026-09-09 실측)
     ```bash
     python scripts/manage_admin.py grant --email 본인@example.com
     ```
3. 재로그인 → 내비게이션에 **"관리자 조회"** 메뉴 표시, `/admin/logs` 접근 가능

### 검증
```bash
curl -s -c c.txt -X POST <라이브>/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"본인@example.com","password":"..."}'
curl -s -b c.txt <라이브>/api/auth/me   # "is_admin": true 확인
```

---

## 테스트 계정 정리 (관리자 확보 후)

과거 검증으로 남은 공백 비밀번호 계정 2건: `space-test@example.com`, `blank-live@example.com`.

관리자 로그인 상태에서 user_id 조회 후 삭제:
```bash
# user_id는 관리자 화면(/admin/logs) 또는 DB에서 확인
curl -s -b c.txt -X DELETE <라이브>/api/admin/users/<user_id>
# 응답: {"user_id":N,"email":"space-test@example.com"}
```
대화 기록·세션·재설정 토큰이 함께 삭제된다(FK CASCADE). 자기 자신/다른 관리자는 삭제 불가(400).

---

## 로그 조회 API 클라이언트 (DB 접근 없이)

로그 조회는 **API만으로** 가능하다 — `scripts/logs_client.py`가 로그인(세션 쿠키) 후 `GET /api/me/chats`·`GET /api/admin/chats`를 호출한다. DB 파일 접근·SQL 권한이 없는 환경(Railway 웹 셸 외부, 운영 URL만 있는 상황)에서 기록 검증에 쓰라.

```bash
# 내 대화 로그 최신 50건 (시간은 KST 표기)
python3 scripts/logs_client.py my --base https://서비스-URL --email me@example.com --password-

# 성공 기록만 2페이지(최대 100건 — before_id 커서 자동 추적)
python3 scripts/logs_client.py my --base ... --email ... --password- --status success --pages 2

# 스크립트 조합용 원문 JSON
python3 scripts/logs_client.py my --base ... --email ... --password- --json

# 관리자: 전체 기록 조회 — 열람 사유는 admin_logs_viewed 감사 이벤트에 기록된다
python3 scripts/logs_client.py all --base ... --email ... --password- --reason "배포 후 영속성 확인"

# 특정 사용자 기록만
python3 scripts/logs_client.py all --base ... --email ... --password- --user-id 12 --reason "계정 문의 대응"
```

- 비밀번호는 `--password-`로 표준 입력에서 읽는 것을 권장(커맨드 히스토리에 남지 않음). 세션 쿠키는 디스크에 저장하지 않는다.
- `my`는 관리자여도 **본인 기록만** 반환한다(서버 계약 — API.md 참고). `all`은 명시적 관리자 권한이 없으면 403.
- `docs/RAILWAY_DEPLOY.md`의 "영속화·운영 증빙"(재배포 후 질문 유지 확인)은 이 클라이언트의 `--json` 출력과 대조로 수행할 수 있다.
- 회귀 테스트: `tests/integration/test_logs_client.py` (MockTransport 기반 — 로그인·필터·커서·권한).

---

## 레거시 폴백 제거 기준 (비밀번호 페퍼 마이그레이션 완료 판정)

페퍼 도입(2026-09-09) 이전 가입자는 **다음 로그인 때 자동 재해싱**된다. 진행률 확인:

```bash
curl -s -b c.txt <라이브>/api/admin/security/password-hashes
# {"total":N,"peppered":M,"legacy":K}
```

- `legacy == 0` 이 되면 `app/services/security.py`의 `verify_password_legacy`와
  `app/routers/auth.py`의 레거시 재해싱 분기를 제거하는 PR을 올린다.
- 레거시 사용자가 남은 채 폴백을 제거하면 해당 계정은 로그인할 수 없게 되므로
  **반드시 0을 확인한 뒤에만** 제거한다.
- 마이그레이션이 끝나지 않은 사용자에게는 비밀번호 재설정(메일)로 스스로 갱신하게 할 수 있다.

## 백업/복원 실측 기록 (2026-09-12)

- 백업 실행: 1회차 2026-09-10 11:04 UTC, 2회차 2026-09-12 13:31 UTC —
  `python scripts/backup_db.py /data/app.db --backup-dir /data/backups --keep 7`
  출력: `integrity=ok sha256=e6d8b40c…`, keep=7 (캡처 `docs/evidence/02-backup-sha256.png`)
- **RPO 실측**: 수동 실행 간격 최대 2일 → 현재 RPO ≤ 48시간.
  목표 24h(BACKUP_RESTORE.md) 대비 미달 — 일 1회 자동화(스케줄러)를 남은 과제로 명시한다.
- **복원 드릴 실측**: 최신 백업을 `/tmp` 사본으로 복원·검증 — 무결성 `ok`,
  users 24행 / chat_logs 91행 확인, 소요 **0.1초 미만**(사본 복원·검증 기준).
  전체 절차(서비스 중지→사전 백업→교체→재기동) 포함해도 목표 RTO 1시간 이내 여유.
  (캡처 `docs/evidence/03-restore-drill.png`, 볼륨 마운트 `01-volume.png`)
