"""표준 이벤트 로그 — CONTRIBUTING.md §1.5의 로그 컨벤션 준수.

형식: event=<이름> key=value key=value  (grep/파싱 용이)
이벤트 이름·정의는 CONTRIBUTING.md §1.5의 등록 목록을 참고한다.
실제 기록 위치는 라우트와 AI 클라이언트에서 확인한다.
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
    """질문 내용의 앞 limit자(기본 50자)를 반환한다.

    짧은 질문은 전체가 남으며 민감정보 마스킹을 보장하지 않는다.
    """
    return text if len(text) <= limit else text[:limit] + "…"
