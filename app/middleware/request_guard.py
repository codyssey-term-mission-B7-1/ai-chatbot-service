"""운영 문서 게이트·교차 출처 상태 변경 차단 미들웨어(#75, #150)."""

from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.policies import DOCS_PATHS, SECURITY_HEADERS, STATE_CHANGING_METHODS


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
