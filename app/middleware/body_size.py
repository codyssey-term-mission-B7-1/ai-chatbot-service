"""요청 바디 크기 상한 미들웨어 — 메모리 DoS 방어(413)."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.policies import SECURITY_HEADERS


async def body_size_guard(request: Request, call_next):
    """요청 바디 상한. Content-Length 헤더로 미리 막는다.

    대용량 업로드를 받지 않는 서비스이므로 1 MiB 기본값으로 메모리 DoS와 로그 오염을 막는다.
    파싱(검증 에러)보다 앞에서 끊어 413으로 응답한다. 청크 전송에 대한 누적 읽기 방어는
    인프라 레벨(로드밸런서/엣지)에서 추가로 막는 것을 전제로 둔다(#HARDENING_BACKLOG B5).
    """
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
