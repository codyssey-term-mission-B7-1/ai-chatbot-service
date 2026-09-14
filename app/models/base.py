"""모델 공용 — UTC 기준 시각 기본값.

DB에는 UTC로만 저장한다(표시 계층에서 KST 변환 — docs/LOGGING.md 시간 정책 D-23).
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
