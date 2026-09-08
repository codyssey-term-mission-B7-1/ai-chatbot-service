"""FastAPI 진입점. 미들웨어 순서·오류 응답·로깅 계약을 한곳에서 정의한다."""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, engine
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
    """없는 테이블만 생성한다. 기존 열/FK 변경이나 데이터 삭제는 수행하지 않는다."""
    Base.metadata.create_all(bind=engine)
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
        response.headers.setdefault(key, value)
    return response


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
    max_age=60 * 60 * 24 * 7,
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
    summary="헬스체크",
    description="status/version/provider 선택 모드. 외부 AI 연결 성공을 검증하지 않습니다.",
)
def health():
    return {
        "status": "ok",
        "version": app.version,
        "ai_mode": "demo" if not settings.ai_api_key else "real",
    }
