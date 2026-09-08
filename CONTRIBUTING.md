# 팀 개발·PR·검증 규칙

현재 구현과 일치하는 명령·파일을 사용한다. 개념 예제만으로 구현/운영이 완료됐다고 주장하지 않는다.

## 역할과 기여

역할 배정은 README의 현재 표와 이슈 assignee, CODEOWNERS를 기준으로 한다. 실제 작성자·커미터는 사실대로 기록한다. 공용 Git 설정 오류의 정정은 SHA별 실제 작업자 확인이 필요하다.

과제의 개인별 유의미한 커밋/PR 요구는 실제 작업과 검증으로 확인한다. 이름 재배정·의미 없는 커밋 분할·가짜 리뷰로 대체하지 않는다. 현재 역할 수 4/3/4/2가 “각자 3개” 기준을 충족하는지는 팀/원문 요구 확인이 필요하며 자동 재배정하지 않는다.

## 브랜치·커밋

- `main ← develop ← feature/#이슈번호-설명`
- `feature/`, `fix/`, `docs/`, `chore/`를 목적에 맞게 사용한다.
- 예: `fix/#27-history-context`, `docs/#13-evidence-index`
- 커밋: `type(scope): 설명 (#이슈번호)`. 실제로 무엇을 왜 바꿨는지 적는다.
- 작업 한 단위씩 커밋한다. 서로 다른 기능을 점수용으로 섞거나 임의로 분할하지 않는다.
- 비밀번호·API 키·쿠키·.env 실제 값을 커밋/PR/로그에 넣지 않는다.

## PR·병합

- 통상 `develop` 대상 PR → 작성자 외 리뷰어 확인 → 병합. 배포는 develop→main PR.
- Merge commit을 사용한다. 현재 main/develop 룰셋은 Merge commit만 허용한다. Squash/Rebase 허용으로 문서화하지 않는다.
- 본문에 작업·테스트·영향 범위·환경·화면 증빙을 적는다. 400줄 내외가 권장이나 통합 수정이 크면 논리별 커밋과 검토 순서를 명시한다.
- 리뷰가 없다고 임의로 승인한 것으로 처리하지 않는다. 대체 리뷰어 지정/긴급 예외는 담당자가 명시적으로 승인하고 기록한다.
- 관리자 예외가 필요한 긴급 복구·이력 정리는 사전 승인·원본 백업·정확한 SHA 검증·즉시 보호 복구가 필요하다. 무흔적 변경을 보장하지 않는다.
- `Closes #N`은 기본 브랜치 대상 병합 등 GitHub 조건을 만족할 때 자동 종료된다. develop PR에서 종료를 추정하지 않는다.
- 이슈는 완료 조건을 실제로 검증한 후 닫는다. 운영/실 AI/개인 기여가 남아 있으면 구현 완료 부분과 외부 차단 사유를 구분한다.

## 코드 스타일·실제 검사 명령

```bash
pip install -r requirements-dev.txt
ruff check app tests
black --check app tests
isort --check-only app tests
pytest --cov=app --cov-report=term-missing
```

- Black/isort의 프로필·100자 기준은 `pyproject.toml`, ruff는 `ruff.toml`을 따른다.
- 필요한 경우 `black app tests`, `isort app tests`로 포맷한 뒤 위 검사를 다시 실행한다.
- 라우트, 서비스, repositories, 모델, 스키마의 책임을 구분한다.
- 외부 AI는 async HTTPX, DB 작업은 SQLAlchemy Session을 사용한다.
- 프론트 fetch/검증 로직은 `static/js/`로 분리하고 사용자/AI 문자열은 textContent/Jinja 자동 이스케이프로 표시한다.
- 새로운 설정·정책은 환경변수의 기본값·단위·허용 범위를 함께 명시한다.

## 테스트 구조

- `tests/unit/`: 스키마·AI 정책·설정·문맥·로깅·백업·프론트 순수 함수
- `tests/integration/`: 가입/로그인, 접근 제어, 대화/저장/조회, 관리자 권한, HTTP 시간 예산, HTML
- 실제 테스트 파일 이름을 참고한다. 존재하지 않는 test_auth.py나 개념용 fixture를 복사해 쓰지 않는다.
- 테스트 DB는 메모리/임시 파일만 사용한다. 외부 AI 키/운영 DB를 사용하지 않는다.
- 타임아웃은 임의로 시간이 오래 걸렸다는 추측 대신, 제어된 루프백 서버와 실제 HTTPX로 검사한다.
- 로컬 합성 테스트 결과를 운영 배포·실 AI 성공으로 제출하지 않는다.

## 입력·로그·민감정보

- 문자 수=Unicode 코드 포인트. 비밀번호는 bcrypt 72 UTF-8 바이트 제약을 별도 적용한다.
- 기본 질문 길이 1000은 설정으로 바꿀 수 있으나 프론트에도 같은 값을 전달한다.
- 오류 응답은 `docs/API.md`의 상태/형식을 따른다. 검증 오류에 비밀번호·질문 원문을 되돌려 넣지 않는다.
- 표준 로그는 `docs/LOGGING.md`의 15종. 새 이벤트를 추가할 때 등록·목적·필드·테스트를 함께 갱신한다.
- 표준 이벤트는 stderr, 값은 필요한 경우 JSON 인용/이스케이프. 요청 원문 대신 길이·상태를 기록한다.
- HTTP 수신 이벤트는 1회. 검증 전 session_user_id와 검증된 user_id를 구분한다.
- DB/입력 값을 포함할 수 있는 예외 원문/SQL 파라미터는 공개 로그에 남기지 않는다.

## UI·재평가 증빙

```bash
pip install -r requirements-evidence.txt
python -m playwright install --with-deps chromium
python scripts/capture_local_evidence.py --output artifacts/local-ui
```

이 검증은 임시 로컬 DB·Fake AI와 실제 Chromium을 사용한다. 오류 UI는 모의 504로 검사한다. 실제 HTTPX 타임아웃은 별도 통합 테스트에서 검증한다. 운영 실기기/실 AI 검증은 환경과 결과를 따로 명시한다.

31개 항목의 현재 코드 근거와 남은 외부 작업은 `docs/EVALUATION_CHECKLIST.md`, 발견 사항의 수정 연결은 `docs/VERIFICATION.md`를 기준으로 한다. 평가 대상 SHA와 **실제 코드 파일 전체**를 포함하고, 링크만 적으면 평가기가 따라 읽는다고 가정하지 않는다.
