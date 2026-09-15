"""감사 이벤트·요청 로그의 DB 영속화 — best-effort(기록 실패가 본 요청에 영향 없음)(#189).

보존 한도: policies.ADMIN_LOG_KEEP_ROWS를 넘으면 오래된 행부터 잘라낸다(1% 확률 트리밍).
"""

import json
import logging
import random

from sqlalchemy import func, select

from app.models import AuditEvent, RequestLog
from app.policies import ADMIN_LOG_KEEP_ROWS

logger = logging.getLogger("app.recorder")

_TRIM_PROBABILITY = 0.01


def _session():
    """세션 팩토리를 호출 시점에 조회한다 — 테스트가 교체해도 앱과 같은 DB를 쓴다."""
    from app import database

    return database.SessionLocal()


def record_event(event: str, *, fields: dict) -> None:
    """이벤트 1건을 DB에 기록한다. 이미 마스킹된 필드 딕셔너리를 받는다."""
    try:
        user_id = fields.get("user_id")
        with _session() as db:
            db.add(
                AuditEvent(
                    event=event,
                    user_id=(
                        user_id
                        if isinstance(user_id, int) and not isinstance(user_id, bool)
                        else None
                    ),
                    request_id=str(fields.get("request_id") or "")[:20],
                    fields_json=json.dumps(
                        {k: v for k, v in fields.items() if k not in ("user_id", "request_id")},
                        ensure_ascii=False,
                        separators=(",", ":"),
                        default=str,
                    ),
                )
            )
            db.commit()
        _maybe_trim(AuditEvent)
    except Exception:
        logger.debug("event DB 기록 실패 — 무시", exc_info=True)


def record_request(
    *, method: str, path: str, status: int, user_id: int | None, latency_ms: int, request_id: str
) -> None:
    """API 요청 1건을 DB에 기록한다. 실패는 조용히 무시한다."""
    try:
        with _session() as db:
            db.add(
                RequestLog(
                    method=method[:8],
                    path=path[:255],
                    status=status,
                    user_id=(
                        user_id
                        if isinstance(user_id, int) and not isinstance(user_id, bool)
                        else None
                    ),
                    latency_ms=max(0, int(latency_ms)),
                    request_id=str(request_id or "")[:20],
                )
            )
            db.commit()
        _maybe_trim(RequestLog)
    except Exception:
        logger.debug("request DB 기록 실패 — 무시", exc_info=True)


def _maybe_trim(model) -> None:
    """1% 확률로 보존 한도 초과분을 삭제한다 — 매 행 삭제 검사를 피하기 위한 트레이드오프."""
    if random.random() >= _TRIM_PROBABILITY:
        return
    try:
        with _session() as db:
            max_id = db.scalar(select(func.max(model.id)))
            if max_id is None or max_id <= ADMIN_LOG_KEEP_ROWS:
                return
            deleted = db.query(model).filter(model.id <= max_id - ADMIN_LOG_KEEP_ROWS).delete()
            db.commit()
            if deleted:
                logger.debug("log trim: %s %d행", model.__tablename__, deleted)
    except Exception:
        logger.debug("log trim 실패 — 무시", exc_info=True)
