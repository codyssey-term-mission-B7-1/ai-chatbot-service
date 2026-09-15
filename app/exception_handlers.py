"""전역 예외 핸들러 — 422 정규화와 500 마스킹(#150)."""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.audit import E
from app.logging_config import log_event
from app.policies import REQUEST_ID_CHARS, SECURITY_HEADERS

logger = logging.getLogger("app")


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


async def unhandled_exception_handler(request: Request, exc: Exception):
    """일관된 500 + 보안 헤더. SQL/입력/키가 포함될 수 있는 예외 원문은 로깅하지 않는다."""
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:REQUEST_ID_CHARS])
    log_event(
        logger,
        E.UNHANDLED_ERROR,
        path=request.url.path,
        error=type(exc).__name__,
        request_id=request_id,
        level=logging.ERROR,
    )
    return JSONResponse(
        status_code=500,
        headers={**SECURITY_HEADERS, "X-Request-ID": request_id},
        content={"detail": "서버에 문제가 생겼어요. 잠시 후 다시 시도해 주세요. (error: INTERNAL)"},
    )


def register(app: FastAPI) -> None:
    """예외 핸들러를 앱에 등록한다 — main.py는 이 함수만 호출한다."""
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
