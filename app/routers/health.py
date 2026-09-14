"""운영 엔드포인트 — /health(라이트 헬스체크)·/readyz(readiness probe)(#150).

main.py에서 분리했다. 계약(docs/API.md) 변경은 없다.
- /health: 프로세스 기동 여부만(DB·외부 호출 없음). build로 실제 서빙 배포 식별.
- /readyz: DB SELECT 1 + 스키마 동기화 상태. 실패 시 503으로 트래픽 유입을 막는다.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import engine
from app.logging_config import log_event
from app.policies import SECURITY_HEADERS
from app.audit import E

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
    from app.database import schema_sync

    if schema_sync["status"] == "ok":
        schema_field = "ok"
    elif schema_sync["status"] == "error":
        schema_field = f"error:{schema_sync['error']}"
    else:
        schema_field = "pending"
    return {
        "status": "ok",
        "version": request.app.version,
        "ai_mode": "demo" if not settings.ai_api_key else "real",
        "build": settings.build_sha,
        # 스키마 동기화 결과 진단 — 2026-09-13 스키마 미반영 사고 이후 로그 말고
        # 헬스체크로 상태가 바로 보일 수 있게 했다. ok / error:<예외타입> / pending.
        "schema": schema_field,
    }


@router.get(
    "/readyz",
    summary="준비 상태 체크",
    description="DB 연결 등 핵심 의존성을 검증합니다. readiness probe에 사용하세요.",
)
def readyz(request: Request):
    """DB에 SELECT 1을 날려 1초 안에 응답하지 못하면 503.

    로드밸런서가 /readyz로 트래픽을 넣을지 결정한다. 프로세스는 떠 있지만 DB 장애가
    있을 때 503으로 빠르게 실패해서 트래픽을 다른 인스턴스로 돌린다.
    """
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
    from app.database import schema_sync

    # DB는 살아도 스키마 동기화가 실패했다면(마이그레이션 미반영) 서비스 불가.
    if schema_sync["status"] == "error":
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
