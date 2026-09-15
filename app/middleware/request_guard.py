"""운영 문서 게이트·교차 출처 상태 변경 차단 미들웨어(#75, #150)."""

from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.policies import DOCS_PATHS, SECURITY_HEADERS, STATE_CHANGING_METHODS


async def request_guard(request: Request, call_next):
    """운영 문서 게이트와 교차 출처 상태 변경 차단(#75)."""
    if not settings.docs_enabled and request.url.path in DOCS_PATHS:
        return JSONResponse(
            status_code=404, content={"detail": "Not Found"}, headers=SECURITY_HEADERS
        )
    if request.method in STATE_CHANGING_METHODS:
        origin = request.headers.get("origin", "")
        origin_host = urlparse(origin).netloc if origin else ""
        if origin_host and origin_host != request.url.netloc:
            return JSONResponse(
                status_code=403,
                content={"detail": "허용되지 않은 요청 출처예요."},
                headers=SECURITY_HEADERS,
            )
    return await call_next(request)
