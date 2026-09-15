"""요청 단위 표준 이벤트 로깅 미들웨어 — request_received / request_finished."""

import asyncio
import logging
import time
import uuid

from fastapi import Request

from app.audit import E
from app.enums import SessionKey
from app.exception_handlers import unhandled_exception_handler
from app.logging_config import REQUEST_ID, log_event
from app.policies import REQUEST_ID_CHARS

logger = logging.getLogger("app")


async def log_requests(request: Request, call_next):
    """HTTP 수신 1회 + 종료 1회. 검증 전 세션 ID와 검증된 계정 ID는 구분한다.

    처리되지 않은 예외를 여기서 500으로 변환하는 이유는 보안 결정이다(#75):
    예외를 다시 던지면 ASGI 서버(uvicorn)가 원문 트레이스백(SQL·입력값 포함 가능)을
    서버 로그에 통째로 남기므로, 마스킹된 응답만 나가도록 이 층에서 마무리한다.
    이 미들웨어 바깥층(세션·보안헤더 등)의 오류는 전역 핸들러가 최후 안전망으로 처리한다.
    """
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
            session_user_id=session.get(SessionKey.USER_ID) if isinstance(session, dict) else None,
            request_id=request_id,
        )
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers.setdefault("X-Request-ID", request_id)
        return response
    except asyncio.CancelledError:
        status_code = 499
        raise
    except Exception as exc:
        return await unhandled_exception_handler(request, exc)
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
