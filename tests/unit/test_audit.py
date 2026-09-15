"""이벤트 카탈로그 정합성 — app/audit.E가 로그 이벤트 이름의 단일 소스다(#151)."""

import re

from app import audit
from app.logging_config import EVENTS

EXPECTED_EVENT_COUNT = 38  # 카탈로그 변경은 의도된 변경이어야 한다 — 수치로 강제한다


def test_catalog_values_follow_event_naming():
    for key, value in vars(audit.E).items():
        if key.isupper():
            assert isinstance(value, str), key
            assert re.fullmatch(r"[a-z][a-z0-9_]*", value), key


def test_catalog_has_no_duplicates():
    values = [value for key, value in vars(audit.E).items() if key.isupper()]
    assert len(values) == len(set(values))


def test_logging_events_derive_from_catalog():
    assert EVENTS == audit.ALL_EVENTS


def test_catalog_size_is_deliberate():
    assert len(audit.ALL_EVENTS) == EXPECTED_EVENT_COUNT
