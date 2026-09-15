"""응답 보안 헤더 미들웨어 — policies.SECURITY_HEADERS를 모든 응답에 일괄 적용(#75, #150)."""

from fastapi import Request

from app.config import settings
from app.policies import DOCS_PATHS, SECURITY_HEADERS


async def security_headers(request: Request, call_next):
    """일반/처리된 오류 응답에 헤더 추가. 미처리 500은 예외 핸들러에서도 동일 적용."""
    response = await call_next(request)
    for key, value in SECURITY_HEADERS.items():
        if (
            key == "Content-Security-Policy"
            and settings.docs_enabled
            and request.url.path in DOCS_PATHS
        ):
            continue
        response.headers.setdefault(key, value)
    return response
