"""설정 경계 강제 — .env.example의 모든 키는 Settings 필드여야 한다(#152, D-25).

분류 규칙: 환경마다 달라지는 값→Settings(.env) / 불변 정책→policies.py.
.env.example에만 있고 Settings에 없는 키는 죽은 문서다 — 이 테스트가 잡는다.
"""

import re
from pathlib import Path

from app.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_env_example_keys_exist_in_settings():
    env = (ROOT / ".env.example").read_text()
    keys = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", env, re.M))
    fields = {f.upper() for f in Settings.model_fields}
    unknown = keys - fields
    assert not unknown, f"Settings에 없는 키가 .env.example에 있음: {sorted(unknown)}"


def test_policy_constants_are_not_env():
    """불변 정책이 실수로 Settings로 새지 않았는지 확인."""
    forbidden = {"max_password_chars", "content_security_policy", "request_id_chars"}
    fields = set(Settings.model_fields)
    assert not forbidden & fields
