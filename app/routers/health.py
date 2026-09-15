"""운영 엔드포인트 — /health(라이트 헬스체크)·/readyz(readiness probe)(#150)."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.audit import E
from app.config import settings
from app.database import engine, schema_sync
from app.enums import SchemaSyncStatus
from app.logging_config import log_event
from app.policies import SECURITY_HEADERS

router = APIRouter(tags=["ops"])
logger = logging.getLogger("app")


@router.get(
    "/health",
    summary="헬스체크(라이트)",
    description=(
        "프로세스 기동 여부만 확인합니다(DB·외부 호출 없음). "
        "로드밸런서·kubelet liveness에 적합합니다. "
        "build는 CD가 주입한 배포 지문(커밋 SHA)으로, 실제로 서빙 중인 배포를 식별합니다."
    ),
)
def health(request: Request):
    if schema_sync["status"] == SchemaSyncStatus.OK:
        schema_field = SchemaSyncStatus.OK
    elif schema_sync["status"] == SchemaSyncStatus.ERROR:
        schema_field = f"error:{schema_sync['error']}"
    else:
        schema_field = SchemaSyncStatus.PENDING
    return {
        "status": "ok",
        "version": request.app.version,
        "ai_mode": "demo" if not settings.ai_api_key else "real",
        "build": settings.build_sha,
        "schema": schema_field,
    }


@router.get(
    "/readyz",
    summary="준비 상태 체크",
    description="DB 연결 등 핵심 의존성을 검증합니다. readiness probe에 사용하세요.",
)
def readyz(request: Request):
    """DB에 SELECT 1을 날려 1초 안에 응답하지 못하면 503."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        log_event(logger, E.READYZ_DB_FAILURE, level=logging.ERROR)
        return JSONResponse(
            status_code=503,
            headers=SECURITY_HEADERS,
            content={"status": "not_ready", "reason": "database_unavailable"},
        )
    if schema_sync["status"] == SchemaSyncStatus.ERROR:
        log_event(
            logger,
            E.READYZ_SCHEMA_FAILURE,
            error=schema_sync["error"],
            level=logging.ERROR,
        )
        return JSONResponse(
            status_code=503,
            headers=SECURITY_HEADERS,
            content={
                "status": "not_ready",
                "reason": "schema_sync_failed",
                "error": schema_sync["error"],
            },
        )
    return {"status": "ready", "version": request.app.version}
