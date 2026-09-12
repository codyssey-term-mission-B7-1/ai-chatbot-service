"""FastAPI 진입점. 미들웨어 순서·오류 응답·로깅 계약을 한곳에서 정의한다."""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import engine, init_db
from app.logging_config import REQUEST_ID, log_event, setup_logging
from app.policies import SECURITY_HEADERS
from app.routers import admin, auth, chat, logs, pages

setup_logging()
logger = logging.getLogger("app")
REPOSITORY_URL = "https://github.com/codyssey-term-mission-B7-1/ai-chatbot-service"
DESCRIPTION = f"""
로그인한 사용자의 질문에 AI가 응답하고, 같은 사용자의 성공 Q/A를 문맥으로 사용합니다.

### 처리 순서
질문 검증 → 성공 문맥 조회 → AI 응답 수신 → DB 저장 시도 → 사용자에게 HTTP 응답.
DB 저장 실패 시 `status=success`라도 `chat_id=-1`일 수 있습니다.
AI_TIMEOUT_SEC는 AI 호출 전체 예산(재시도/대기 포함)이며 DB 처리 시간은 제외합니다.

### 인증과 관리자
서명된 세션 쿠키를 사용합니다(JWT 아님). API 비로그인은 401, 관리 권한 부족은 403입니다.
관리자 권한은 기본적으로 없으며 서버 운영자의 명시적 부여가 필요합니다.

### 문서
- [API 명세]({REPOSITORY_URL}/blob/main/docs/API.md)
- [공통 규칙]({REPOSITORY_URL}/blob/main/CONTRIBUTING.md)
- [역할별 작업]({REPOSITORY_URL}/blob/main/docs/TODO.md)
"""


@asynccontextmanager
async def lifespan(application: FastAPI):
    """스키마 동기화(Alembic 마이그레이션 또는 create_all+stamp).

    테이블이 이미 있으면 누락 마이그레이션만 적용하고, 빈 DB/인메모리는 create_all 후
    head 스탬프로 최신 상태를 마킹한다. Alembic이 FK·열 변경을 안전하게 처리한다.
    """
    # 모든 모델이 Base.metadata에 등록되도록 명시적으로 임포트한다(그렇지 않으면
    # autogenerate와 create_all이 릴레이션을 찾지 못한다).
    import app.models  # noqa: F401

    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version="0.2.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "회원가입·서명 쿠키 세션"},
        {"name": "chat", "description": "AI 응답 → DB 저장 시도 → HTTP 응답"},
        {"name": "logs", "description": "사용자별 대화 조회·성공 문맥 복원"},
        {"name": "admin", "description": "명시적 관리자 권한이 필요한 전체 조회"},
        {"name": "ops", "description": "기동 상태 확인. AI 연결 성공을 뜻하지 않음"},
    ],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """일반/처리된 오류 응답에 헤더 추가. 미처리 500은 아래 핸들러에서도 동일 적용."""
    response = await call_next(request)
    for key, value in SECURITY_HEADERS.items():
        # /docs·/redoc의 Swagger UI는 CDN 자산을 쓴다 — 개발·검증 전용 경로는 CSP에서 제외(#75).
        if (
            key == "Content-Security-Policy"
            and settings.docs_enabled
            and request.url.path in DOCS_PATHS
        ):
            continue
        response.headers.setdefault(key, value)
    return response


_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
DOCS_PATHS = frozenset({"/docs", "/docs/", "/redoc", "/redoc/", "/openapi.json"})


@app.middleware("http")
async def body_size_guard(request: Request, call_next):
    """요청 바디 상한. Content-Length 헤더로 미리 막는다.

    대용량 업로드를 받지 않는 서비스이므로 1 MiB 기본값으로 메모리 DoS와 로그 오염을 막는다.
    파싱(검증 에러)보다 앞에서 끊어 413으로 응답한다. 청크 전송에 대한 누적 읽기 방어는
    인프라 레벨(로드밸런서/엣지)에서 추가로 막는 것을 전제로 둔다(#HARDENING_BACKLOG B5).
    """
    limit = settings.max_request_body_bytes
    if limit > 0:
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > limit:
            return JSONResponse(
                status_code=413,
                headers=SECURITY_HEADERS,
                content={"detail": "요청 본문이 너무 커요."},
            )
    return await call_next(request)


@app.middleware("http")
async def request_guard(request: Request, call_next):
    """운영 문서 게이트와 교차 출처 상태 변경 차단(#75).

    - DOCS_ENABLED=false면 /docs·/redoc·/openapi.json을 404로 숨긴다(운영 기본).
    - 상태 변경 메서드에 Origin 헤더가 있고 출처 호스트가 다르면 403. 같은 출처
      브라우저 요청은 통과하고 curl/스모크처럼 Origin을 보내지 않는 클라이언트도 통과한다.
    - log_requests 안쪽에 둬서 차단된 요청도 request_finished 로그에 남는다.
    """
    if not settings.docs_enabled and request.url.path in DOCS_PATHS:
        return JSONResponse(
            status_code=404, content={"detail": "Not Found"}, headers=SECURITY_HEADERS
        )
    if request.method in _STATE_CHANGING_METHODS:
        origin = request.headers.get("origin", "")
        origin_host = urlparse(origin).netloc if origin else ""
        if origin_host and origin_host != request.url.netloc:
            return JSONResponse(
                status_code=403,
                content={"detail": "허용되지 않은 요청 출처예요."},
                headers=SECURITY_HEADERS,
            )
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """HTTP 수신 1회 + 종료 1회. 검증 전 세션 ID와 검증된 계정 ID는 구분한다."""
    request_id = uuid.uuid4().hex[:20]
    request.state.request_id = request_id
    token = REQUEST_ID.set(request_id)
    started = time.perf_counter()
    is_api = request.url.path.startswith("/api/")
    status_code = 500
    if is_api:
        session = request.scope.get("session", {})
        log_event(
            logger,
            "request_received",
            method=request.method,
            path=request.url.path,
            session_user_id=session.get("user_id") if isinstance(session, dict) else None,
            request_id=request_id,
        )
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers.setdefault("X-Request-ID", request_id)
        return response
    except Exception as exc:
        return await unhandled_exception_handler(request, exc)
    except asyncio.CancelledError:
        status_code = 499  # 로그용: 요청 취소. 실제 499 응답 전송을 보장하는 것은 아니다.
        raise
    finally:
        if is_api:
            log_event(
                logger,
                "request_finished",
                method=request.method,
                path=request.url.path,
                user_id=getattr(request.state, "authenticated_user_id", None),
                status=status_code,
                request_id=request_id,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        REQUEST_ID.reset(token)


# 마지막 등록이 가장 바깥: Session → request logger → security headers → router.
# SessionMiddleware는 서명만 하며 암호화하지 않는다. 쿠키에는 user_id/email_fp만 넣는다.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=settings.session_max_age_hours * 3600,  # 기본 24시간(#74)
    https_only=not settings.debug,
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """유효성 오류에 사용자가 입력한 비밀번호·질문 원문을 다시 싣지 않는다."""
    details = []
    for error in exc.errors():
        item = {key: error[key] for key in ("loc", "type", "msg") if key in error}
        item["loc"] = [
            (
                part.encode("utf-8", "backslashreplace").decode("utf-8")
                if isinstance(part, str)
                else part
            )
            for part in item["loc"]
        ]
        item["msg"] = str(item["msg"]).encode("utf-8", "backslashreplace").decode("utf-8")
        context = {
            key: value
            for key, value in error.get("ctx", {}).items()
            if key in {"max_length", "min_length", "ge", "gt", "le", "lt"}
        }
        if context:
            item["ctx"] = context
        details.append(item)
    return JSONResponse(status_code=422, content={"detail": details}, headers=SECURITY_HEADERS)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """일관된 500 + 보안 헤더. SQL/입력/키가 포함될 수 있는 예외 원문은 로깅하지 않는다."""
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:20])
    log_event(
        logger,
        "unhandled_error",
        path=request.url.path,
        error=type(exc).__name__,
        request_id=request_id,
        level=logging.ERROR,
    )
    return JSONResponse(
        status_code=500,
        headers={**SECURITY_HEADERS, "X-Request-ID": request_id},
        content={
            "detail": "서버에 문제가 생겼어요. 잠시 후 다시 시도해 주세요. " "(error: INTERNAL)"
        },
    )


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(logs.router)
app.include_router(admin.router)
app.include_router(pages.router)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get(
    "/health",
    tags=["ops"],
    summary="헬스체크(라이트)",
    description=(
        "프로세스 기동 여부만 확인합니다(DB·외부 호출 없음). "
        "로드밸런서·kubelet liveness에 적합합니다."
    ),
)
def health():
    return {
        "status": "ok",
        "version": app.version,
        "ai_mode": "demo" if not settings.ai_api_key else "real",
    }


@app.get(
    "/readyz",
    tags=["ops"],
    summary="준비 상태 체크",
    description="DB 연결 등 핵심 의존성을 검증합니다. readiness probe에 사용하세요.",
)
def readyz():
    """DB에 SELECT 1을 날려 1초 안에 응답하지 못하면 503.

    로드밸런서가 /readyz로 트래픽을 넣을지 결정한다. 프로세스는 떠 있지만 DB 장애가
    있을 때 503으로 빠르게 실패해서 트래픽을 다른 인스턴스로 돌린다.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        log_event(logger, "readyz_db_failure", level=logging.ERROR)
        return JSONResponse(
            status_code=503,
            headers=SECURITY_HEADERS,
            content={"status": "not_ready", "reason": "database_unavailable"},
        )
    return {"status": "ready", "version": app.version}
