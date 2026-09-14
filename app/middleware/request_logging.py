"""요청 단위 표준 이벤트 로깅 미들웨어 — request_received / request_finished."""

import asyncio
import logging
import time
import uuid

from fastapi import Request

from app.audit import E
from app.exception_handlers import unhandled_exception_handler
from app.logging_config import REQUEST_ID, log_event
from app.policies import REQUEST_ID_CHARS

logger = logging.getLogger("app")


async def log_requests(request: Request, call_next):
    """HTTP 수신 1회 + 종료 1회. 검증 전 세션 ID와 검증된 계정 ID는 구분한다."""
    request_id = uuid.uuid4().hex[:REQUEST_ID_CHARS]
    request.state.request_id = request_id
    token = REQUEST_ID.set(request_id)
    started = time.perf_counter()
    is_api = request.url.path.startswith("/api/")
    status_code = 500
    if is_api:
        session = request.scope.get("session", {})
        log_event(
            logger,
            E.REQUEST_RECEIVED,
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
                E.REQUEST_FINISHED,
                method=request.method,
                path=request.url.path,
                user_id=getattr(request.state, "authenticated_user_id", None),
                status=status_code,
                request_id=request_id,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        REQUEST_ID.reset(token)
