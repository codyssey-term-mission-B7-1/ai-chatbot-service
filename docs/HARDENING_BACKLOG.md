# 하드닝 백로그 (인프라 의존 항목)

전문가 평가에서 지적된 항목 중 **코드 변경만으로는 막을 수 없고 인프라/외부 서비스가 필요한 것**을
정리한다. PR #116(fix/expert-feedback-hardening)에서 즉시 조치 가능한 항목은 모두 반영했고,
아래 항목은 추후 마일스톤으로 남긴다.

## 즉시 조치 완료 (PR #116)

- 회원가입/비밀번호 재설정 IP 기반 레이트리밋 (SlidingWindowLimiter, 메모리 기반).
- 채팅/로그인/회원가입/비밀번호 재설정 429 응답 `Retry-After` + 한국어 대기 안내(약 M분 S초).
- /readyz 엔드포인트(DB `SELECT 1`) 추가 — /health는 라이트 버전 유지.
- AI 시스템 프롬프트 안전 규칙 6개 + 간단한 프롬프트 인젝션 탐지(경고문 자동 삽입).
- 비밀번호 블랙리스트(흔한 비밀번호 40여 개, 단순 반복 비밀번호 거부).
- 이메일 로컬파트 길이 제한(64자, RFC 5321).
- 요청 바디 크기 상한 미들웨어(기본 1 MiB, Content-Length 우선 차단).

## 백로그

### B1. CAPTCHA / Turnstile (회원가입·로그인·비밀번호 재설정)
- 필요 인프라: Cloudflare Turnstile 또는 reCAPTCHA v2/v3 (비용·키 관리).
- 메모리 기반 IP 레이트리밋은 봇을 느리게만 할 뿐 막지는 못한다. 분산 IP 우회에 취약하다.
- 대안: 이메일 인증 링크(아래 B2)로 1차 방어.

### B2. 이메일 인증 (회원가입 직후 이메일 소유권 확인)
- 필요 인프라: SMTP/Resend (현재는 비밀번호 재설정만 메일 발송).
- 가짜 이메일 계정 대량 생성을 막고, 계정 탈취 시 복구 채널을 확보한다.
- 기존 스키마 `users.is_verified` 컬럼 + 이메일 템플릿 + 토큰 저장소 추가 필요.

### B3. 분산 레이트리밋 (Redis/Valkey)
- 현재 메모리 기반 limiter는 프로세스 내부에서만 동작한다. 다중 워커/다중 인스턴스/재시작
  환경에서 한도가 초기화되거나 인스턴스별로 분산된다.
- Redis Sliding-Window 또는 Token Bucket로 전환 필요.
- 연동: client_ip() 헬퍼가 신뢰할 수 있는 프록시(X-Forwarded-For) 지원도 함께.

### B4. Webhook / 취약점 스캐너
- 필요 인프라: Snyk/Dependabot 자동 의존성 업그레이드, OWASP ZAP 정기 스캔.

### B5. 요청 바디 크기 제한 — 엣지/로드밸런서 단계에서도
- 앱 레벨 1 MiB는 방어선 하나일 뿐. Railway/Cloudflare 앞단에서 `client_max_body_size`
  같은 제한을 함께 걸어 앱 프로세스에 트래픽이 도달하기 전에 차단해야 한다.

### B6. Structured JSON 로깅을 프로덕션 기본값으로
- 현재는 사람이 읽는 key=value 로그. 로그 수집기(Datadog/Loki/ELK)로 집계하려면 JSON 출력
  옵션(LOG_FORMAT=json)을 추가하고 운영에서 기본으로 켜야 한다. 로그 마스킹 정책도
  재검토 필요(현재는 이메일 평문을 안 남기고 도메인/핑거프린트만 남김).

### B7. 비밀번호 재사용/이력 제한
- 로그인 감사(audit_logs)와 연동해 최근 N개 비밀번호 재사용 금지 — 로그인 이력 저장소
  스키마와 관리자 대시보드가 필요하다(현재는 대화 로그만 저장).

### B8. MFA (TOTP/WebAuthn)
- 이메일 탈취나 비밀번호 유출 시 최후 방어선. 관리자 계정 우선 적용 권장.

### B9. 운영용 액션 (계정 잠금/비밀번호 강제 리셋 API)
- 관리자 대시보드 UI + CLI에 기능이 일부만 있다. 의심 계정에 대한 강제 로그아웃/리셋
  워크플로우를 문서화한다.

## 코드 안내 주석

코드베이스 곳곳에 남겨둔 TODO로 백로그 항목을 가리킨다:

- `app/services/rate_limit.py:client_ip()` — 신뢰 프록시 X-Forwarded-For 처리 필요.
- `app/services/rate_limit.py` limiter 인스턴스들 — 다중 워커에서 Redis로 전환 필요.
- `app/routers/auth.py` 회원가입 주석 — CAPTCHA/이메일 인증은 다음 마일스톤.
- `app/services/context.py` — 프롬프트 인젝션 탐지는 규칙 기반 1차 방어이며, 추후
  전용 분류기나 OpenAI Moderation API 등 검토.
