"""표준 이벤트 로그 — team-conventions.md의 로그 컨벤션 준수.

형식: event=<이름> key=value key=value  (grep/파싱 용이)
이벤트 6종: request_received / ai_call_start / ai_call_success / ai_call_fail
            db_save_success / db_save_fail
주의: API 키·비밀번호·세션 토큰은 절대 로그에 남기지 않는다.
"""
import logging

SYSTEM_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=SYSTEM_LOG_FORMAT)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields) -> None:
    parts = [f"event={event}"] + [f"{k}={v}" for k, v in fields.items()]
    logger.log(level, " ".join(parts))


def truncate(text: str, limit: int = 50) -> str:
    """개인정보 보호 — 로그에 남기는 질문은 최대 50자."""
    return text if len(text) <= limit else text[:limit] + "…"
