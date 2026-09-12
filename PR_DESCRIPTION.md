## 🚨 먼저 긴급 안내
사용자께서 메시지 본문에 GitHub 개인 액세스 토큰(`ghp_puyat...NEIJa`)을 평문으로 남기셨습니다. **이 토큰은 이제 폐기된 것으로 간주해야 합니다.** GitHub Settings → Developer settings → Personal access tokens 에서 즉시 해당 토큰을 Revoke 하고 새로 발급받으세요. 본 작업에서는 보안 상의 이유로 이 토큰을 전혀 사용하지 않았으며(로컬 커밋만 완료), 토큰을 파일이나 원격에 저장하지 않았습니다. 푸시는 본인 인증된 환경에서 직접 아래 명령으로 진행해 주세요.

---

# PR: 하드닝 감사 반영 — AI 파이프라인·보안·DB 풀 버그 수정 + 감사 문서

## 배경
EXPERT_INTERVIEW_GUIDE.md 작성을 위해 저장소를 전수 조사하는 과정에서 발견된 정확도·보안·운영 이슈를 정리하고, 당장 조치 가능한 항목을 이 PR에서 수정했다. 향후 마일스톤 백로그와 과제 범위 내에서 인정하는 한계는 `docs/AUDIT_HARDENING.md`에 분류해 남겼다.

## 변경 요약
**이 PR 조치 항목 (8건)**:
1. **[HIGH] AI 페이로드 정책 누락 버그 수정** — `build_payload()`가 정의만 되어 있고 실제 `_attempts()`에서 쓰이지 않아 `AI_MAX_TOKENS`/`AI_TEMPERATURE`가 제공사 기본값으로 무시되던 문제 해제 → 실제로 호출하도록 변경하고 회귀 테스트 추가.
2. **[MED] AI 응답 잘림(끊김) 미표시** — `finish_reason=length`를 검사해 말줄임 표식 `…(응답이 길이 제한으로 잘렸어요)`을 붙여 문맥 오염과 사용자 혼란 방지.
3. **[MED] AI 클라이언트 이중 타임아웃 정리** — `asyncio.timeout`(전체 예산)과 `httpx timeout`이 중복으로 걸려 재시도 경로에서 예산이 깨지는 문제를 정리. per-attempt 타임아웃은 연결/쓰기/풀/읽기로 세분화.
4. **[LOW] AI 엔드포인트 중복 접미사 버그** — 기본 예시 `AI_BASE_URL=https://api.openai.com/v1/chat/completions`에서 `/chat/completions`가 한 번 더 붙는 버그 → normalize 시 중복 스트립 추가.
5. **[LOW] httpx keep-alive/커넥션 풀 튜닝** — AI 호출 시 매 요청 TCP 핸드셰이크가 반복되던 비효율 개선.
6. **[MED] 비밀번호 재설정 메일 실패 로그 정보 누출 축소** — `error=str(exc)` 대신 예외 타입 이름만 기록해 API 키/응답 body가 로그에 남지 않도록 (#104 정책 일관).
7. **[HIGH/dev] DB engine 초기화 SQLite dialect 분기** — SQLite에서 `pool_size/max_overflow` 인자로 TypeError가 나던 문제를 dialect 분기로 해소, Postgres 전환 시 풀 옵션 자동 적용.
8. **감사 문서 2종 추가** — `docs/AUDIT_HARDENING.md`(미흡/문제/조치/백로그/한계 집계표), `EXPERT_INTERVIEW_GUIDE.md`(3인 전문가 3시간 인터뷰 질문 가이드).

## 테스트
- pytest: **223 → 226 passed** (회귀 테스트 3건 추가)
  - `test_build_payload_is_signed_with_server_policy`: 페이로드에 max_tokens/temperature 포함 여부
  - `test_normalize_endpoint_dedupes_double_suffix`: 중복 접미사 정리
  - `test_extract_content_flags_length_truncation`: 잘림 표식
- ruff / black / isort: 통과

## 백로그 (다음 마일스톤에 티켓으로 이관)
보안: 회원가입 rate limit + 이메일 인증/캡차, 세션 탈취 대응, 프롬프트 인젝션 기본 방어, 출력 모더레이션.
운영: Redis/DB 기반 rate limit, 외부 모니터링/알림, Alembic + Postgres 전환, 오프사이트 백업.
제품/UX: SSE 스트리밍 응답, 만족도 피드백 + golden set 자동 평가, 채팅 세션 구분, 제공자 폴백.
상세 내용·추정 공수·근거는 `docs/AUDIT_HARDENING.md` §2 참조.

## 인정(과제 범위 내 한계, 억지로 붙이지 않음)
- 단일 워커 + SQLite 전제 (Postgres 전환 전까지)
- AI 품질/안전 평가 파이프라인 (별도 마일스톤으로 분리)
- PIPA 개인정보 영향평가 (법적 검토 필요)

## 리뷰 포인트
- `app/services/ai_client.py`의 `_attempts()` 변경이 기존 `test_total_budget_includes_backoff_and_does_not_claim_an_unstarted_retry` 테스트 의미를 유지하는지 (재시도 이벤트가 sleep 이후 기록됨 — 전체 예산 중 타임아웃 시 이벤트가 남지 않아야 함)
- `app/database.py` dialect 분기가 SQLite 기존 동작을 변경하지 않음을 확인
- 이메일 실패 로그가 장애 디버깅을 불가능하게 만들지 않는지 (예외 타입만으로 충분한 추적이 되는가)

## 변경 파일
```
app/services/ai_client.py            # F-1~F-5
app/database.py                      # F-7
app/routers/auth.py                  # F-6
tests/unit/test_ai_client.py         # 회귀 테스트 3건
docs/AUDIT_HARDENING.md              # 감사 보고서
EXPERT_INTERVIEW_GUIDE.md            # 전문가 인터뷰 가이드
```

## 검증 방법
```bash
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
pytest -q                       # 226 passed
ruff check app tests
black --check app tests
isort --check-only app tests
```

## 로컬 푸시/PR 방법 (토큰은 새로 발급한 것을 쓰세요)
```bash
# 1) GitHub에서 기존 ghp_puyatQ... 토큰 Revoke 후 새 PAT 발급
# 2) 로컬에서 인증 (GitHub CLI 또는 HTTPS 개인 액세스 토큰)
git push -u origin fix/hardening-audit-fixes
# 3) 아래 URL에서 PR 생성 (base=main ← compare=fix/hardening-audit-fixes)
#    https://github.com/codyssey-term-mission-B7-1/ai-chatbot-service/pull/new/fix/hardening-audit-fixes
```

---

### 주의사항
- 기존 팀은 PR 규칙(ADR-006)에 따라 Squash 금지이므로 **Merge commit 생성** 방식으로 머지해 주세요.
- CD 게이트 통과를 확인하려면 `AI_API_KEY`/`SESSION_SECRET`/`PASSWORD_PEPPER`/`RAILWAY_TOKEN`/`DEPLOY_URL` Secrets가 최신 상태인지 사전 확인.
- 이 브랜치는 `main`에서 딴 것이 아니라 팀이 통상 쓰는 `develop` → `main` 플로우와 다릅니다. 팀 컨벤션대로 하려면 PR base를 `develop`으로 두고 이후 `main`으로 릴리스 머지하는 것이 더 적절합니다.
