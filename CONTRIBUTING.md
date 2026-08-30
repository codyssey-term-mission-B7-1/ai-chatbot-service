# 팀 워킹 규칙 — 컨벤션 · PR 규정 · 테스트 전략

> 웹 기반 AI 챗봇 서비스 (FastAPI + SQLite, 4인 팀) 공통 규칙
> 이 문서는 저장소에 `CONTRIBUTING.md`로 넣고, 위반 시 PR 리뷰에서 반려하는 기준으로 사용한다.

---

# 1. 컨벤션

## 1.1 브랜치 네이밍

```
main          ← 배포용. 직접 push 금지 (PR로만 병합)
develop       ← 통합 브랜치. 기능 완성 PR은 여기로
feature/*     ← 기능 개발
fix/*         ← 버그 수정
docs/*        ← 문서 작업
chore/*       ← 환경설정, 의존성 등
hotfix/*      ← main 긴급 수정 (드물게 사용)
```

**브랜치 이름 규칙**: `종류/#이슈번호-짧은설명` (kebab-case)

| 좋은 예 | 나쁜 예 |
|---|---|
| `feature/#4-signup-api` | `feature` (내용 없음) |
| `fix/ai-timeout-504` | `jimin-work` (사람 이름) |
| `docs/api-specs` | `test123` |

## 1.2 커밋 컨벤션 (Conventional Commits)

**형식**: `type(scope): 제목 (#이슈번호)`

| type | 용도 | 예시 |
|------|------|------|
| `feat` | 기능 추가 | `feat(auth): 회원가입 API 추가 (#4)` |
| `fix` | 버그 수정 | `fix(ai): 타임아웃 시 504 대신 500 나오던 버그 수정` |
| `docs` | 문서 | `docs: README에 환경변수 설정 방법 추가` |
| `test` | 테스트 | `test(chat): 타임아웃 통합 테스트 추가` |
| `refactor` | 동작 unchanged 리팩터링 | `refactor(db): 세션 처리를 의존성 주입으로 변경` |
| `style` | 포맷/스타일 | `style: black 재적용` |
| `chore` | 설정, 의존성 | `chore: ruff 설정 추가` |

**규칙**
1. 제목은 50자 이내, 마침표 없음, 현재형 동사로 끝냄 (추가/수정/삭제)
2. **1 커밋 = 1 논리 단위** — 회원가입 API와 CSS 수정을 한 커밋에 섞지 않는다
3. 커밋 메시지에 **API 키, 비밀번호, .env 내용 절대 금지**
4. 본문 필요 시 제목 한 줄 띄우고 상세 설명 (무엇을/왜)
5. 과제 채점 기준이 "팀원별 유의미한 커밋 10회+"이므로, **하루 작업을 2~3개 논리 단위로 쪼개 커밋**한다 (`작업 끝날 때 한 방 커밋` 금지)

```
나쁜 예: ㅇㅋ / 수정 / final / update2
좋은 예: feat(chat): 문맥 유지 위해 직전 5개 Q/A를 프롬프트에 포함 (#7)
```

## 1.3 코드 스타일 (Python)

| 항목 | 규칙 |
|------|------|
| 포매터 | **Black** (라인 100자), 임포트 정렬 **isort**, 린터 **ruff** — 커밋 전 `make lint` 실행 |
| 타입 힌트 | 공개 함수/라우트 핸들러의 매개변수·반환 타입 필수 |
| docstring | 공개 함수/클래스에 Google 스타일 한 줄 이상 |
| 네이밍 | 함수·변수 `snake_case`, 클래스 `PascalCase`, 상수 `UPPER_SNAKE` |
| 비동기 | AI API 호출이 있는 라우트는 `async def` + `httpx.AsyncClient` (동기 호출로 스레드 막힘 방지) |
| 매직 넘버 금지 | 타임아웃, 컨텍스트 개수 등은 `app/config.py` 상수 or 환경변수로 |
| 함수 길이 | 가이드 40줄 이내, 깊이 3단계 이내 (절대 기준 아님) |
| 민감정보 | 코드에 키/비번 직접 작성 금지 — 반드시 `os.environ` / pydantic-settings |

**프론트(HTML/JS/CSS)**: 파일명 kebab-case(`chat-page.js`), JS 변수 `camelCase`, 인덴트 2공백, `fetch` 호출은 `static/js/`로 분리(인라인 스크립트 최소화).

## 1.4 네이밍 — DB / API / 환경변수

**DB** — 테이블 복수형 snake_case, PK `id`, FK `테이블단수_id`, 시각 필드 `created_at`/`updated_at` (UTC)

```sql
users(id, email UNIQUE, password_hash, nickname, created_at)
chat_logs(id, user_id FK, question, answer, latency_ms, status, created_at)
```

**API** — 리소스 기반 REST, 동사는 URL에 쓰지 않음

```
POST /api/auth/signup     회원가입
POST /api/auth/login      로그인
POST /api/auth/logout     로그아웃
GET  /api/me             내 정보 (인증 필요)
POST /api/chat            질문 → AI 응답 (인증 필요)
GET  /api/me/chats        내 대화 로그 조회 (인증 필요)
GET  /health              헬스체크 (인증 불필요)
```

**환경변수** — UPPER_SNAKE, `.env.example`에 이름·설명만 (값은 각자 `.env`)

```
AI_API_KEY=          # AI 제공사 API 키
AI_MODEL=            # 모델명
AI_TIMEOUT_SEC=10    # AI 호출 타임아웃(초)
AI_MAX_RETRIES=1     # 재시도 횟수
CONTEXT_TURNS=5      # 컨텍스트로 넘길 직전 Q/A 개수
SESSION_SECRET=      # 세션/JWT 서명 키
DATABASE_URL=sqlite:///./app.db
```

## 1.5 로그 컨벤션

표준 이벤트 이름은 **고정된 snake_case 세트**를 사용한다 (채점 증빙 자료).

```
INFO  event=request_received user_id=12 path=/api/chat
INFO  event=ai_call_start user_id=12 request_id=abc123
INFO  event=ai_call_success request_id=abc123 latency_ms=1240
ERROR event=ai_call_fail request_id=abc123 reason=timeout latency_ms=10000
INFO  event=db_save_success user_id=12 chat_id=987
ERROR event=db_save_fail user_id=12 reason=<exception 요약>
```

규칙:
1. `event=` 은 위 6종만 사용 (새 이벤트 추가 시 이 문서에 먼저 등록)
2. 키=값 쌍은 `key=value` 스페이스 구분 (로그 파싱/grep 쉽게)
3. 사용자 질문 전문은 로그에 남기지 않음(최대 50자) — 개인정보·비용 고려
4. **API 키, 비밀번호, 세션 토큰은 어떤 로그에도 출력 금지**
5. 에러는 `logger.exception()` 사용해 스택트레이스 확보

---

# 2. PR 규정

## 2.1 기본 흐름

```
feature/#N-xxx  →  PR  →  리뷰어 1명 승인  →  develop 에 merge
develop  →  (배포 시점) PR  →  main  →  배포
```

- PR 크기 가이드: **변경 400줄 이내**. 넘치면 기능을 쪼개 여러 PR로
- 1 PR = 1 이슈. PR 본문에 `Closes #N` 작성 (머지 시 이슈 자동 종료)
- 모든 PR에는 작성자 외 **리뷰어 1명 필수** (같은 영역 아닌 사람 우선 → 교차 학습)
- 리뷰 SLA: **다음 작업일 이내** 반영. 24시간 방치 시 DM 1회 후 임의 승인 가능

## 2.2 PR 제목 & 템플릿

**제목**: 커밋 컨벤션과 동일하게 `type(scope): 제목 (#이슈번호)`

`.github/pull_request_template.md` (복사해서 사용):

```markdown
## 📌 작업 내용
- (이슈 #N) 무엇을 왜 했는지 1~3줄

## 🔍 변경 요약
- 변경한 파일/함수 요약

## 🧪 테스트 결과
- [ ] 유닛 테스트 추가 & 통과 (`pytest tests/unit -k 관련키워드`)
- [ ] 통합 테스트 통과 (`pytest tests/integration`)
- [ ] 수동 확인 (방법 + 결과 요약)

## 📸 스크린샷 (UI 변경 시 필수)

## ✅ 셀프 체크리스트
- [ ] ruff/black 통과
- [ ] 민감정보 없음 (.env, 키, 토큰 미포함)
- [ ] 새 로그 이벤트 사용 시 로그 컨벤션 문서에 등록
- [ ] API 변경 시 API 명세 문서 업데이트
```

## 2.3 리뷰 규칙

**리뷰 코멘트 접두어** (리뷰이가 우선순위를 파악하게):

| 접두어 | 의미 | 반영 |
|--------|------|------|
| `[MUST]` | 반드시 수정 (버그, 보안, 컨벤션 위반) | 머지 전 필수 |
| `[SUG]` | 제안 (더 나은 방법) | 논의 후 선택 |
| `[Q]` | 질문 | 답변 필수 |
| `[NIT]` | 사소한 지적 (오타 등) | 선택 |

- 리뷰어는 "코드가 틀렸다"가 아니라 **"이렇게 하면 어떤 상황에서 문제"** 로 이유를 적는다
- `[MUST]` 반영 후 작성자가 `push` → 리뷰어 재확인 후 Approve
- 컨플릭트는 **PR 작성자가** 해결
- Approve 조건(리뷰어 체크): 요구사항 충족 / 테스트 있음 / 민감정보 없음 / 로그·네이밍 컨벤션 준수

## 2.4 머지 전략 — ⚠️ Squash 금지

> **과제 채점 기준이 "팀원별 커밋 10회 이상"이므로 커밋 히스토리를 반드시 보존해야 한다.**

| 방식 | 사용 여부 | 이유 |
|------|-----------|------|
| **Merge commit** | ✅ 기본 사용 | 개별 커밋 전부 보존 + 머지 흔적 남음 |
| Rebase and merge | ✅ 허용 | 커밋 보존, 히스토리 선형 |
| **Squash and merge** | ❌ 금지 | 여러 커밋이 1개로 합쳐져 커밋 수 증빙 손해 |

**브랜치 보호 설정** (저장소 Settings → Branches):
- `main`, `develop` 모두: ✅ "Require a pull request before merging" + "Require 1 approval" — 직접 push 차단
- "Require status checks" (CI 도입 후): ruff + pytest 통과 시에만 머지

## 2.5 라벨 & 역할 태그

| 라벨 | 의미 |
|------|------|
| `be` / `fe` | 백엔드 / 프론트엔드 |
| `auth` `ai` `db` `ui` `deploy` `docs` | 담당 영역 |
| `bug` `enhancement` | 버그 / 개선 |
| `blocked` | 막힘 — 즉시 스탠드업 공유 |

주 1회(마일스톤 날) 각자 PR/커밋 수를 확인: **목표 = 인당 PR 1~2개/주, 커밋 2~3개/주.**

---

# 3. 테스트 전략 — 유닛 테스트 & 풀(통합·E2E) 테스트

## 3.1 3단계 구조와 도구

| 레벨 | 대상 | 도구 | 시기 |
|------|------|------|------|
| **유닛** | 함수/클래스 단위 (검증, 해싱, 컨텍스트, AI 클라이언트) | pytest | 기능 구현과 동시에 |
| **통합(풀)** | API 전체 흐름 (회원가입→로그인→채팅→로그조회, 접근제어, 타임아웃) | pytest + FastAPI TestClient + httpx | D7~D9 |
| **E2E 스모크** | 배포된 실서버 대상 시나리오 | bash + curl 스크립트 | 배포 후 매일 + 평가 전 |

```bash
pip install pytest pytest-asyncio httpx pytest-cov ruff black isort
```

**디렉터리 구조**

```
tests/
├── conftest.py            # 공용 fixture (DB, 클라이언트, Fake AI)
├── unit/
│   ├── test_schemas.py        # 입력 검증
│   ├── test_auth.py           # 해싱, 토큰
│   ├── test_ai_client.py      # 타임아웃/에러 매핑
│   └── test_context.py        # 컨텍스트 빌더
└── integration/
    ├── test_auth_flow.py      # 가입/로그인/접근제어
    └── test_chat_flow.py      # 채팅 파이프라인, 타임아웃, 로그 저장
scripts/
└── e2e_smoke.sh               # 실서버 풀 테스트
```

## 3.2 유닛 테스트

**원칙**
1. **AI API 실호출 금지** — 의존성 주입으로 `FakeAIProvider` 갈아끼우거나 httpx mock 사용 (비용·속도·안정성)
2. 테스트명: `test_{대상}_{조건}_{기대결과}` — 실패 시 무엇이 잘못됐는지 이름만으로 알 수 있게
3. AAA 패턴 (Arrange 준비 → Act 실행 → Assert 확인)
4. 해피케이스 + **실패 케이스 최소 1개**를 세트로 작성
5. DB는 인메모리 SQLite로 격리, 테스트 간 영향 없게 fixture에서 생성/삭제

**필수 유닛 테스트 목록 (채점 대응)**

| 모듈 | 테스트 | 대응 요구사항 |
|------|--------|---------------|
| schemas | 빈 질문/공백만 → ValidationError | 입력 검증 |
| schemas | 1000자 초과 질문 → ValidationError | 입력 검증(길이 제한) |
| auth | 비밀번호 해싱 후 검증 성공/실패 | 회원 인증 |
| ai_client | TimeoutException → AI_TIMEOUT 에러 매핑 | 타임아웃 처리 |
| ai_client | 4xx/5xx 응답 → AI_ERROR 매핑 | 예외 처리 |
| context | 히스토리 10개 중 최근 N개만 선택 | 컨텍스트 전략 |
| context | 히스토리 0개일 때도 정상 동작 | 컨텍스트 전략 |
| db | chat_log 저장 성공 시 id 반환 | 로그 저장 |

**예시 코드**

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.services.ai import get_ai_provider

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSession = sessionmaker(bind=engine)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class FakeAIProvider:
    """AI API를 흉내내는 페이크 — 테스트에서 실호출을 대체"""
    def __init__(self, reply="테스트 응답입니다."):
        self.reply = reply
        self.error = None

    async def generate(self, messages, timeout):
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture()
def fake_ai():
    provider = FakeAIProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_ai_provider, None)
```

```python
# tests/unit/test_schemas.py
import pytest
from pydantic import ValidationError
from app.schemas import ChatRequest


def test_chat_request_empty_question_rejected():
    # 빈 입력/공백만 있는 질문은 거부되어야 한다
    with pytest.raises(ValidationError):
        ChatRequest(question="   ")


def test_chat_request_over_1000_chars_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(question="가" * 1001)


def test_chat_request_valid_question_accepted():
    req = ChatRequest(question="배포 방법 알려줘")
    assert req.question == "배포 방법 알려줘"
```

```python
# tests/unit/test_ai_client.py
import asyncio

import httpx
import pytest

from app.services.ai_client import AIClient, AITimeoutError


def test_ai_client_timeout_maps_to_custom_error(monkeypatch):
    # httpx가 TimeoutException을 던지면 AITimeoutError로 변환되어야 한다
    def raise_timeout(*args, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx.AsyncClient, "post", raise_timeout)
    client = AIClient(api_key="test-key", timeout_sec=0.001)

    with pytest.raises(AITimeoutError):
        asyncio.run(client.generate([{"role": "user", "content": "hi"}]))
```

> 위 예시는 서비스 코드가 `AIClient.generate()`에서 httpx 예외를 커스텀 예외(`AITimeoutError`)로 변환한다는 구조를 가정한 것. 실제 구현에 맞게 조정하되, 핵심은 **"AI API가 죽어도 예외가 라우트 밖으로 새어나가 서버가 죽지 않고, 504 + AI_TIMEOUT 응답으로 변환된다"** 를 테스트하는 것.

```python
# tests/unit/test_context.py
from app.services.context import build_context


def test_context_returns_only_last_n_pairs():
    history = [(f"q{i}", f"a{i}") for i in range(1, 11)]  # 10개
    ctx = build_context(history, n=3)
    assert len(ctx) == 3
    assert ctx[0] == ("q8", "a8")   # 최신 3개만, 오래된 순서 유지


def test_context_with_empty_history_returns_empty():
    assert build_context([], n=5) == []
```

## 3.3 풀 테스트 — 통합(API) 테스트

API를 실제로 묶은 상태에서 **요구사항 시나리오 그대로** 검증한다. 이 테스트가 곧 평가 증빙자료가 된다.

```python
# tests/integration/test_chat_flow.py
import httpx


def signup_and_login(client, email="tester@example.com", password="Test1234!"):
    client.post("/api/auth/signup", json={"email": email, "password": password})
    client.post("/api/auth/login", json={"email": email, "password": password})


def test_chat_blocked_without_login(client):
    # 비로그인 사용자는 채팅 불가 (접근 제어)
    r = client.post("/api/chat", json={"question": "안녕"})
    assert r.status_code == 401


def test_full_chat_pipeline_saves_log(client, fake_ai, db):
    # 가입 → 로그인 → 질문 → AI 응답 → DB 저장 → 내 로그 조회 전체 흐름
    signup_and_login(client)

    r = client.post("/api/chat", json={"question": "배포 방법 알려줘"})
    assert r.status_code == 200
    assert r.json()["answer"] == "테스트 응답입니다."

    logs = client.get("/api/me/chats").json()
    assert len(logs) == 1
    assert logs[0]["question"] == "배포 방법 알려줘"
    assert logs[0]["answer"] == "테스트 응답입니다."
    assert "created_at" in logs[0]          # 최소 추적 필드: 시각


def test_ai_timeout_returns_504_and_server_survives(client, fake_ai):
    # 타임아웃 강제 유발 → 안내 응답 + 서버 비정상 종료 없음
    fake_ai.error = httpx.TimeoutException("timeout")
    signup_and_login(client)

    r = client.post("/api/chat", json={"question": "긴 글 요약해줘"})
    assert r.status_code == 504
    assert "AI_TIMEOUT" in r.json()["detail"]

    assert client.get("/health").status_code == 200   # 서버 생존 확인


def test_context_carried_over_conversation(client, fake_ai):
    # 문맥 유지: 직전 질문이 다음 요청 컨텍스트에 포함되는지 (요청 기록으로 검증)
    signup_and_login(client)
    client.post("/api/chat", json={"question": "오늘 날씨 어때?"})
    client.post("/api/chat", json={"question": "내가 방금 뭘 물어봤지?"})
    assert fake_ai.last_messages[0]["content"].find("오늘 날씨") != -1
```

## 3.4 풀 테스트 — E2E 스모크 (배포 서버 대상)

`scripts/e2e_smoke.sh` — 배포 후 매일 + **평가 직전** 실행. 통과 로그를 캡처해 증빙으로 제출.

```bash
#!/usr/bin/env bash
# 사용법: ./scripts/e2e_smoke.sh https://배포URL
set -e
BASE=${1:?Usage: e2e_smoke.sh <BASE_URL>}
EMAIL="smoke_$(date +%s)@test.local"

echo "① 헬스체크";   curl -sf "$BASE/health" > /dev/null && echo "  OK"
echo "② 회원가입";   curl -sf -X POST "$BASE/api/auth/signup" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"Test1234!\"}" > /dev/null && echo "  OK"
echo "③ 로그인";     curl -sf -c /tmp/cj -X POST "$BASE/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"Test1234!\"}" > /dev/null && echo "  OK"
echo "④ 미로그인 채팅 차단 확인"; \
  test "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/chat" \
  -H 'Content-Type: application/json' -d '{"question":"hi"}')" = "401" && echo "  OK (401)"
echo "⑤ 채팅(실 AI 호출)"; curl -sf -b /tmp/cj -X POST "$BASE/api/chat" \
  -H 'Content-Type: application/json' -d '{"question":"안녕, 한 줄로 자기소개해줘"}' && echo ""
echo "⑥ 내 대화 로그 조회"; curl -sf -b /tmp/cj "$BASE/api/me/chats" | head -c 300 && echo ""
echo "✅ E2E 스모크 통과"
```

**타임아웃 실서버 검증 방법 (평가 시연 대비)**: 서버 env의 `AI_TIMEOUT_SEC=0.001`로 잠시 변경 후 재시작 → 채팅 요청 → 504 + `AI_TIMEOUT` 안내 확인 → 서버 살아있는지 `/health` 확인 → 원복. 과정을 화면 녹화/캡처해 문서에 첨부.

## 3.5 커버리지 & CI

- 커버리지 목표: **전체 60% 이상, 핵심 모듈(auth, ai, chat, db) 80% 권장** — 숫자 자체보다 "핵심 경로가 테스트됐다"가 중요
- 명령: `pytest --cov=app --cov-report=term-missing`

**GitHub Actions** (`.github/workflows/ci.yml`) — PR마다 자동 실행, 통과 시에만 머지:

```yaml
name: CI
on:
  pull_request:
    branches: [develop, main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check app tests
      - run: pytest --cov=app --cov-report=term-missing
```

> CI에 필요한 환경변수는 GitHub 저장소 Secrets에 등록 (테스트는 Fake을 쓰므로 실제 API 키 불필요하게 설계).

## 3.6 역할별 테스트 담당 & 일정 연계

| 담당 | 작성할 테스트 | 시기 |
|------|---------------|------|
| 🔧 A (서버 코어) | `test_auth.py`(해싱/토큰), `test_auth_flow.py`(가입/로그인/401 접근제어) | D4~D5, D7 |
| 🤖 B (AI·데이터) | `test_ai_client.py`(타임아웃 매핑), `test_context.py`, DB 저장 테스트 | D7~D8 |
| 🎨 C (프론트) | UI 수동 체크리스트(빈 입력 차단, 로딩/에러 표시) — 문서화 + 스크린샷 | D7~D8 |
| 🛠 D (운영·품질) | `test_chat_flow.py`(통합 파이프라인, 타임아웃 504), `e2e_smoke.sh`, CI 구축 | D8~D11 |

**Definition of Done (PR 머지 조건)**: 기능 동작 + 테스트 작성·통과 + 관련 문서 업데이트 — 셋 중 하나라도 빠지면 머지하지 않는다.

---

## 부록: 요구사항 ↔ 테스트 매핑 (평가 증빙용)

| 과제 요구사항 | 증빙 테스트 |
|---------------|-------------|
| 빈 입력 차단 등 입력 검증 | `test_chat_request_empty_question_rejected` |
| 로그인한 사용자만 채팅 가능 | `test_chat_blocked_without_login` |
| 질문→AI→응답→저장 파이프라인 | `test_full_chat_pipeline_saves_log` |
| 사용자 기준 로그 조회 | `GET /api/me/chats` 검증 (위 테스트에 포함) |
| 타임아웃 시 서버 생존 + 오류 안내 | `test_ai_timeout_returns_504_and_server_survives` + 실서버 캡처 |
| 문맥 유지 | `test_context_*` 2종 + 데모 시연 |
| 외부 접속 배포 | `e2e_smoke.sh` 통과 로그 |
