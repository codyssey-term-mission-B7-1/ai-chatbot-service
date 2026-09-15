"""모델 공용 — UTC 기준 시각 기본값."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
