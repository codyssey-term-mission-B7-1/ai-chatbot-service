"""FastAPI 애플리케이션 진입점."""
import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, engine
from app.logging_config import log_event, setup_logging
from app.routers import auth, chat, pages

setup_logging()
logger = logging.getLogger("app")

Base.metadata.create_all(bind=engine)  # SQLite 테이블 자동 생성

DESCRIPTION = """
웹 기반 AI 챗봇 서비스 — 로그인한 사용자의 질문을 AI API로 전달해 응답하고,
모든 대화를 DB에 저장해 **사용자별로 추적**할 수 있습니다.

### 핵심 파이프라인
`질문 수신 → 직전 N개 Q/A 컨텍스트 구성 → AI API 호출(타임아웃 보호) → 응답 반환 → 대화 로그 저장`

### 오류 안내
| 코드 | 에러 | 상황 |
|------|------|------|
| 504 | `AI_TIMEOUT` | AI 응답 지연 (AI_TIMEOUT_SEC 초과) |
| 502 | `AI_ERROR` | AI API 호출 실패 |
| 401 | — | 로그인 필요 (챗봇은 인증된 사용자만) |

### 더보기
- API 상세 문서: [docs/API.md](../docs/API.md)
- 컨벤션 규칙: [CONTRIBUTING.md](../CONTRIBUTING.md)
- 역할별 TODO: [docs/TODO.md](../docs/TODO.md)
"""

TAGS_METADATA = [
    {"name": "auth", "description": "회원가입·로그인·로그아웃 — 세션 쿠키 기반 인증"},
    {"name": "chat", "description": "AI 챗봇 파이프라인 (질문 → AI 호출 → 응답 → 로그 저장)"},
    {"name": "ops", "description": "운영 — 헬스체크"},
]

app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version="0.1.0",
    openapi_tags=TAGS_METADATA,
)

# (주의) 아래 커스텀 미들웨어보다 나중에 추가 → Session이 바깥에서 실행됨
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """요청 수신 로그 — /api/* 경로만 남김 (과제: request_received 이벤트)."""
    started = time.perf_counter()
    if request.url.path.startswith("/api"):
        user_id = request.scope.get("session", {}).get("user_id", "-")
        log_event(logger, "request_received", user_id=user_id,
                  method=request.method, path=request.url.path)
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        log_event(logger, "request_finished",
                  path=request.url.path, status=response.status_code,
                  latency_ms=int((time.perf_counter() - started) * 1000))
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """처리 못한 예외도 서버가 죽지 않고 502/안내 응답으로 변환."""
    logger.exception("event=unhandled_error path=%s error=%s", request.url.path, type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": "서버에 문제가 생겼어요. 잠시 후 다시 시도해 주세요. (error: INTERNAL)"},
    )


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(pages.router)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health", tags=["ops"])
def health():
    """헬스체크 — 배포/E2E 스모크에서 서버 생존 확인용."""
    return {"status": "ok", "ai_mode": "demo" if settings.ai_api_key is None else "real"}
