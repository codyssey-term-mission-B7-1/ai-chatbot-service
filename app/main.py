"""FastAPI 진입점 — 조립(composition root)만 담당한다(#150)."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  # 모델 레지스트리 등록 — create_all/autogenerate에 필요
from app import __version__
from app.audit import E
from app.config import settings
from app.database import init_db
from app.exception_handlers import register as register_exception_handlers
from app.logging_config import log_event, setup_logging
from app.middleware import register as register_middleware
from app.routers import register_routers

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
    """스키마 동기화(Alembic 마이그레이션 또는 create_all+stamp)."""
    try:
        init_db()
    except Exception as exc:
        log_event(
            logger,
            E.READYZ_DB_FAILURE,
            reason="init_db_failed",
            error=type(exc).__name__,
            level=logging.ERROR,
        )
    yield


app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version=__version__,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "회원가입·서명 쿠키 세션"},
        {"name": "chat", "description": "AI 응답 → DB 저장 시도 → HTTP 응답"},
        {"name": "logs", "description": "사용자별 대화 조회·성공 문맥 복원"},
        {"name": "admin", "description": "명시적 관리자 권한이 필요한 전체 조회"},
        {"name": "ops", "description": "기동 상태 확인. AI 연결 성공을 뜻하지 않음"},
    ],
)

register_middleware(app)
register_exception_handlers(app)
register_routers(app)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
