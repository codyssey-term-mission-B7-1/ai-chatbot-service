"""챗 파이프라인 — 질문 수신 → AI 호출 → 응답 반환 → 대화 로그 저장."""
import logging
import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.logging_config import log_event, truncate
from app.models import ChatLog, User
from app.schemas import ChatLogOut, ChatRequest, ChatOut
from app.services.ai_client import AIError, AIProvider, AITimeoutError, get_ai_provider
from app.services.context import SYSTEM_PROMPT, build_context

logger = logging.getLogger("app.chat")
router = APIRouter(prefix="/api", tags=["chat"])


def _save_log(db: Session, user_id: int, question: str, answer: str,
              latency_ms: int, status_: str, request_id: str) -> int | None:
    """대화 로그 저장 + db_save_success/fail 로그."""
    log = ChatLog(
        user_id=user_id, question=question, answer=answer,
        latency_ms=latency_ms, status=status_, request_id=request_id,
    )
    try:
        db.add(log)
        db.commit()
        log_event(logger, "db_save_success", user_id=user_id, chat_id=log.id, status=status_)
        return log.id
    except Exception:
        db.rollback()
        log_event(logger, "db_save_fail", user_id=user_id, reason="db_exception",
                  level=logging.ERROR)
        logger.exception("DB 저장 실패")
        return None


@router.post("/chat", response_model=ChatOut,
             summary="질문 → AI 응답 (핵심 파이프라인)",
             description=(
                 "질문 수신 → 직전 N개(CONTEXT_TURNS) Q/A 컨텍스트 구성 → AI API 호출"
                 " → 응답 반환 → 대화 로그 DB 저장. AI 호출은 서버에서만 수행됩니다(키 노출 방지)."
             ),
             responses={
                 401: {"description": "로그인 필요 — 챗봇은 인증된 사용자만 사용 가능"},
                 422: {"description": "입력 검증 실패 (빈 질문 / 1000자 초과)"},
                 502: {"description": "AI 호출 실패 (error: AI_ERROR) — 서버는 종료되지 않음"},
                 504: {"description": "AI 타임아웃 (error: AI_TIMEOUT) — 서버는 종료되지 않음"},
             })
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai: AIProvider = Depends(get_ai_provider),
):
    request_id = uuid.uuid4().hex[:8]
    log_event(logger, "request_received", user_id=user.id, path="/api/chat", request_id=request_id,
              question=truncate(body.question))

    # 1) 컨텍스트 구성: 같은 사용자의 성공한 직전 N개 Q/A
    history = (
        db.query(ChatLog)
        .filter(ChatLog.user_id == user.id, ChatLog.status == "success")
        .order_by(ChatLog.id.desc())
        .limit(settings.context_turns)
        .all()
    )[::-1]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += build_context([(h.question, h.answer) for h in history], settings.context_turns)
    messages.append({"role": "user", "content": body.question})

    # 2) AI 호출 (타임아웃은 클라이언트 내부에서 적용)
    log_event(logger, "ai_call_start", user_id=user.id, request_id=request_id)
    started = time.perf_counter()
    try:
        answer = await ai.generate(messages)
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_event(logger, "ai_call_success", request_id=request_id, latency_ms=latency_ms)
    except (AITimeoutError, httpx.TimeoutException):
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_event(logger, "ai_call_fail", request_id=request_id, reason="timeout",
                  latency_ms=latency_ms, level=logging.ERROR)
        _save_log(db, user.id, body.question, "", latency_ms, "ai_error", request_id)
        raise HTTPException(
            status_code=504,
            detail="현재 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요. (error: AI_TIMEOUT)",
        )
    except AIError:
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_event(logger, "ai_call_fail", request_id=request_id, reason="ai_error",
                  latency_ms=latency_ms, level=logging.ERROR)
        _save_log(db, user.id, body.question, "", latency_ms, "ai_error", request_id)
        raise HTTPException(
            status_code=502,
            detail="AI 서버에 문제가 생겼어요. 잠시 후 다시 시도해 주세요. (error: AI_ERROR)",
        )

    # 3) DB 저장 후 응답
    chat_id = _save_log(db, user.id, body.question, answer, latency_ms, "success", request_id)
    return ChatOut(
        answer=answer,
        latency_ms=latency_ms,
        chat_id=chat_id or -1,
        status="success",
    )


@router.get("/me/chats", response_model=list[ChatLogOut],
            summary="내 대화 로그 조회",
            description="본인 대화 로그만 반환 (사용자 기준 추적). 최신순, limit 최대 200.")
def my_chats(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """내 대화 로그 조회 — 사용자 기준 추적 (타인의 로그는 접근 불가)."""
    return (
        db.query(ChatLog)
        .filter(ChatLog.user_id == user.id)
        .order_by(ChatLog.id.desc())
        .limit(min(limit, 200))
        .all()
    )
