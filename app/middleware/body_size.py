"""요청 바디 크기 상한 미들웨어 — 메모리 DoS 방어(413)."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.policies import SECURITY_HEADERS


async def body_size_guard(request: Request, call_next):
    """요청 바디 상한. Content-Length 헤더로 미리 막는다."""
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
