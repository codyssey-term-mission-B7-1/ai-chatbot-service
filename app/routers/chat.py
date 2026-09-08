"""채팅: 검증 → 성공 문맥 → AI → DB 저장 시도 → HTTP 응답."""

import asyncio
import logging
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.logging_config import log_event
from app.models import User
from app.repositories import chat_logs
from app.schemas import ChatOut, ChatRequest
from app.services.ai_client import AIError, AIProvider, AITimeoutError, get_ai_provider
from app.services.context import SYSTEM_PROMPT, build_context

logger = logging.getLogger("app.chat")
router = APIRouter(prefix="/api", tags=["chat"])


def _save_log(
    db: Session,
    user_id: int,
    question: str,
    answer: str,
    latency_ms: int,
    status_: str,
    request_id: str,
) -> int | None:
    """저장 실패 시 원문/SQL 파라미터 없이 진단 메타데이터만 기록한다."""
    try:
        row = chat_logs.save_log(
            db,
            user_id=user_id,
            question=question,
            answer=answer,
            latency_ms=latency_ms,
            status=status_,
            request_id=request_id,
        )
        log_event(
            logger,
            "db_save_success",
            user_id=user_id,
            chat_id=row.id,
            status=status_,
            request_id=request_id,
        )
        return row.id
    except Exception as exc:
        log_event(
            logger,
            "db_save_fail",
            user_id=user_id,
            reason=type(exc).__name__,
            request_id=request_id,
            level=logging.ERROR,
        )
        return None


@router.post(
    "/chat",
    response_model=ChatOut,
    summary="질문 → AI 응답",
    description=(
        "같은 사용자의 성공 Q/A 문맥 → AI 응답 수신 → DB 저장 시도 → HTTP 응답. "
        "status=success는 AI 성공을 뜻하며 chat_id=-1이면 DB 저장 실패입니다."
    ),
    responses={
        401: {"description": "로그인 필요"},
        422: {"description": "공백 또는 설정된 질문 길이 상한 초과"},
        502: {"description": "AI_ERROR: AI 호출/응답 형식 오류"},
        504: {"description": "AI_TIMEOUT: AI 호출 전체 시간 예산 초과"},
    },
)
async def chat(
    body: ChatRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    request_id = request.state.request_id
    history = chat_logs.successful_context(db, user.id, settings.context_turns)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += build_context([(h.question, h.answer) for h in history], settings.context_turns)
    messages.append({"role": "user", "content": body.question})
    log_event(
        logger,
        "ai_call_start",
        user_id=user.id,
        question_chars=len(body.question),
        context_pairs=len(history),
        request_id=request_id,
    )
    started = time.perf_counter()
    try:
        async with asyncio.timeout(settings.ai_timeout_sec):
            answer = await ai.generate(messages)
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_event(
            logger, "ai_call_success", user_id=user.id, request_id=request_id, latency_ms=latency_ms
        )
    except (AITimeoutError, httpx.TimeoutException, TimeoutError):
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_event(
            logger,
            "ai_call_fail",
            user_id=user.id,
            request_id=request_id,
            reason="timeout",
            latency_ms=latency_ms,
            level=logging.ERROR,
        )
        _save_log(db, user.id, body.question, "", latency_ms, "ai_error", request_id)
        raise HTTPException(
            status_code=504,
            detail=("현재 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요. (error: AI_TIMEOUT)"),
        ) from None
    except AIError:
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_event(
            logger,
            "ai_call_fail",
            user_id=user.id,
            request_id=request_id,
            reason="ai_error",
            latency_ms=latency_ms,
            level=logging.ERROR,
        )
        _save_log(db, user.id, body.question, "", latency_ms, "ai_error", request_id)
        raise HTTPException(
            status_code=502,
            detail=("AI 서버에 문제가 생겼어요. 잠시 후 다시 시도해 주세요. (error: AI_ERROR)"),
        ) from None
    chat_id = _save_log(db, user.id, body.question, answer, latency_ms, "success", request_id)
    return ChatOut(answer=answer, latency_ms=latency_ms, chat_id=chat_id or -1, status="success")
