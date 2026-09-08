# 검출 내용 해결·검증 색인

이 문서는 실제 코드/테스트의 연결표다. **로컬·Fake/모의 HTTP·운영 환경을 구분**한다. 운영 배포나 실 AI가 검증되지 않은 상태를 완료로 표시하지 않는다.

## D01~D19 수정 연결

| ID | 수정 | 자동 검증 |
|---|---|---|
| D01 | Swagger 총괄·태그와 실제 저장 순서/실패 계약 통일 | test_swagger_links_are_absolute_and_descriptions_match_contract |
| D02 | Swagger 문서 링크를 GitHub 절대 URL로 변경 | 동일 테스트 |
| D03 | /logs HTML 비로그인 302, API 401 구분 | test_html_redirects_and_api_auth_errors_are_separate |
| D04 | SessionMiddleware, user_id/email_fp, 서명 쿠키 계약 명시 | test_session_cookie_carries_no_plaintext_email |
| D05 | Session을 바깥에 등록, 수신 이벤트 1회, 세션 ID와 검증 ID 구분 | test_session_is_outermost_and_log_identity_is_explicit / test_one_http_received_event_and_no_question_logging |
| D06 | 예상 밖 500 보안 헤더·종료 로그, 예외 원문 비노출 | test_unhandled_500_has_security_headers_and_finished_log |
| D07 | 8~64 코드 포인트 + UTF-8 72바이트 검증, 500 대신 422 | test_password_byte_boundary_is_a_validation_error |
| D08 | JS 코드 포인트 계산, 서버 길이 설정을 화면에 전달 | test_frontend_counts_codepoints_like_pydantic / 실제 브라우저 체크 |
| D09 | status=success 필터 후 N개 제한, AI와 UI 조회 함수 정합화 | test_success_filter_precedes_limit_and_matches_ai_context |
| D10 | SQLite 조회 시 UTC tzinfo 보정, API Z/화면 UTC 표기 | test_utc_marker_survives_sqlite_roundtrip |
| D11 | AI 호출 전체 deadline(재시도 대기 포함) | test_http_total_budget_returns_504_even_when_chunks_keep_arriving / test_total_budget_includes_backoff_and_does_not_claim_an_unstarted_retry |
| D12 | 잘못된 multipart 타입을 AIError/502로 매핑 | test_malformed_multipart_maps_to_502_and_is_saved |
| D13 | 실제 추가 시도 시작 시에만 ai_retry | test_retry_event_counts_started_additional_attempts |
| D14 | Demo/Real 진단 분리, --require-real 미설정 종료 2 | test_ai_check_fake_result_is_not_a_real_connection_claim |
| D15 | DB 인접 기본 백업·고유 파일명·원본별 세대·0600 | tests/unit/test_tools.py의 backup 테스트 |
| D16 | CD의 미설정 변수는 명시적 기본값/빈 값, DEBUG=false 고정 | 워크플로 정적/모의 CLI 검증, 실제 배포는 별도 |
| D17 | 문맥 실험을 실제 12번째 요청 기준으로 명시 | test_experiment_is_twelve_requests_and_restores_global_settings |
| D18 | 기본 표준 이벤트 stderr 계약 명시 | app/logging_config.py + docs/LOGGING.md |
| D19 | 값 이스케이프·질문 원문 미기록 | test_log_values_escape_newlines_and_do_not_echo_sensitive_fields |

## 추가 기능과 구조

- `app/repositories/`: 사용자·대화 기록 CRUD 계층
- `app/routers/logs.py`: 사용자 로그와 성공 문맥 복원 API
- `app/routers/admin.py`, `/admin/logs`: 명시적 관리자 전용 조회
- `admin_grants`: 기존 users 열을 바꾸지 않는 별도 권한 테이블
- `tests/integration/test_admin.py`: 권한 기본 없음, 비관리자 403, 전체 조회, 본인 API 격리, 즉시 회수

## 재현 명령

```bash
pip install -r requirements-dev.txt
ruff check app tests
black --check app tests
isort --check-only app tests
pytest --cov=app --cov-report=term-missing

# 실제 Chromium이 로컬 앱을 조작한다. 임시 DB·Fake AI만 사용한다.
pip install -r requirements-evidence.txt
python -m playwright install --with-deps chromium
python scripts/capture_local_evidence.py --output artifacts/local-ui
```

`capture_local_evidence.py`는 로컬 서버·브라우저를 실행하고 종료한다. 결과에 소스 코드 해시, 시각, 체크 항목, 각 이미지의 검증 방법을 기록한다. 비밀번호 바이트 제한, Enter/Shift+Enter/합성 IME 이벤트, 중복 전송, 문맥 복원, 오류 UI, 기록·관리자 조회, 모바일 폭을 점검한다.

로딩 캡처는 요청에 지연을 주며, 오류 UI 캡처는 모의 HTTP 504를 사용한다. 이는 실제 AI 지연/운영 장애 증거가 아니다. 실제 HTTPX의 시간 예산은 별도 루프백 HTTP 테스트에서 검증한다.

## 남아 있는 외부 완료 조건

- 실제 AI 제공사 endpoint/model/key로 `ai_check.py --require-real` 성공 및 문맥 품질 확인
- Railway 프로젝트·영구 볼륨·Secrets, 실제 URL, 첫 배포/E2E/복원 드릴
- 팀별 실제 작업·PR/리뷰, 3주 스탠드업·회고, M1/M2/M3 승인
- 역할 담당자로 과거 Author/Committer를 자동 재배정하지 않음

현재 실행 결과와 화면은 `docs/evidence/`의 시각·소스 해시를 함께 확인한다. 새 코드를 과거 PR에서 검증한 것처럼 SHA나 과거 리뷰 기록을 바꾸지 않는다.
