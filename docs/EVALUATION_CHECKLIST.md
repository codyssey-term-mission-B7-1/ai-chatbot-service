# 사전평가 31개 항목의 현재 증빙

원래 평가의 PASS/FAIL을 새 점수로 바꾸지 않는다. 현재 구현·로컬 검증·외부 완료 조건을 구분한다.

| 번호 | 주제 | 현재 근거 | 남은 확인 |
|---|---|---|---|
| #1 | 문제 정의·대상·시나리오 | README §1 | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #2 | 아키텍처·컴포넌트 책임 | README §2 · app/routers/ · app/repositories/ | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #3 | API 요청·응답 예제 | docs/API.md · /openapi.json | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #4 | DB 구조·ERD·제약 | README ERD · app/models.py | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #5 | 사용자별 로그·SQL 조회 | app/routers/logs.py · scripts/check_logs.sql | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #6 | 역할·개인별 기여 증빙 | README 역할표 · docs/commit-audit.md | 실제 개인 기여와 과거 PR의 원래 기록을 대조. 실제 기여 증빙으로 확인한다. |
| #7 | 회원가입 UI | templates/login.html · static/js/auth.js · 로컬 UI 캡처 | 실제 Chromium의 로컬 캡처 제공. 실기기·운영 환경 검증은 별도. |
| #8 | 로그인·세션 발급 | app/routers/auth.py · app/deps.py · Cookie 테스트 | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #9 | 비로그인 접근 차단 | tests/integration/test_auth_flow.py · test_verified_gaps.py | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #10 | 질문 입력·응답 UI | templates/chat.html · static/js/chat.js · 로컬 UI 캡처 | 실제 Chromium의 로컬 캡처 제공. 실기기·운영 환경 검증은 별도. |
| #11 | 서버→AI 호출 흐름 | app/services/ai_client.py | 실제 네이토/선택 제공사 endpoint/model/key와 운영 응답은 별도 검증. |
| #12 | 질문·응답 DB 저장 | app/repositories/chat_logs.py · test_chat_flow.py | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #13 | 관리자 전체 로그 조회 | app/routers/admin.py · templates/admin-logs.html · test_admin.py | 관리자 기능 구현·로컬 권한 테스트 완료. 운영 권한은 기본 미부여; 신뢰된 운영자가 신원 확인 후 명시 부여. |
| #14 | 타임아웃·예외·서버 생존 | test_ai_http_budget.py · test_verified_gaps.py | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #15 | 오류 코드·사용자 안내 | docs/API.md · static/js/form-utils.js | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #16 | 입력 검증 | app/schemas.py · test_schema_edge_cases.py | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #17 | 라우터·서비스·모델·스키마 분리 | app/routers/ · app/services/ · app/repositories/ | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #18 | 목적별 라우트 분리 | auth/chat/logs/admin/pages 라우트 분리 | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #19 | Pydantic 실제 사용 | app/schemas.py 및 라우트 response_model | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #20 | 인증 DI·미들웨어 분리 | app/deps.py · SessionMiddleware | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #21 | 모델·세션·CRUD 계층 | app/models.py · app/database.py · app/repositories/ | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #22 | 민감정보 제외 정책 | .gitignore · 실제 비밀값 제외 | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #23 | .env.example 제공 | .env.example · README 실행 방법 | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #24 | PR·병합 증빙 | GitHub PR 기록 · 이 PR의 CI · 과거/현재 SHA 구분 | 실제 개인 기여와 과거 PR의 원래 기록을 대조. 실제 기여 증빙으로 확인한다. |
| #25 | 실제 REST 엔드포인트 | docs/API.md · OpenAPI 경로 자동 검증 | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #26 | 로그인 제한의 근거 | docs/ACCESS_CONTROL.md 설계 근거와 한계 | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #27 | AI 키 서버 측 사용 | app/services/ai_client.py 서버 헤더 · 프론트 /api/chat 호출 | 실제 네이토/선택 제공사 endpoint/model/key와 운영 응답은 별도 검증. |
| #28 | 재시도·대체 동작 정책 | docs/API.md 재시도/시간 예산 · test_ai_policies.py | 실제 네이토/선택 제공사 endpoint/model/key와 운영 응답은 별도 검증. |
| #29 | 로그 목적 매핑 | docs/LOGGING.md 목적/필드/집계표 | 구현 및 로컬 테스트 근거 확인. 실제 평가 대상에 전체 소스를 포함. |
| #30 | 실제 운영 로그 증빙 | 표준 이벤트 구현·로컬 서버 로그 | 운영 배포 후 실제 로그 증거 필요. 로컬/Fake 자료를 운영 로그로 표시하지 않음. |
| #31 | 문서·Git·PR 증빙 대조 | 정상 PR/CI 기록과 실제 기여 증빙 | 실제 개인 기여와 과거 PR의 원래 기록을 대조. 실제 기여 증빙으로 확인한다. |

## 현재 공개 URL·실 AI·팀 활동은 외부 조건

- 이전 main이 문서 8개뿐이었던 시각과 현재 소스는 다르다. 평가 대상 SHA/파일 목록부터 확인한다.
- 역할 카드 #12/#35/#44의 실배포, #1/#2/#45의 팀 활동/기여 조건은 코드 작성만으로 완료되지 않는다.
- 로컬 화면과 검증 방법: [실행 증빙](evidence/LOCAL_VERIFICATION.md). 코드별 회귀 테스트: [검출 내용 해결](VERIFICATION.md).
