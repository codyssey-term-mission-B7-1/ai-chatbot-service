"""유닛 테스트 — 입력 검증 (빈 입력 차단, 길이 제한)."""
import pytest
from pydantic import ValidationError

from app.schemas import ChatRequest, SignupIn


def test_chat_request_empty_question_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(question="")


def test_chat_request_whitespace_only_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(question="    \n\t  ")


def test_chat_request_over_max_length_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(question="가" * 1001)


def test_chat_request_valid_question_stripped():
    req = ChatRequest(question="  배포 방법 알려줘  ")
    assert req.question == "배포 방법 알려줘"


def test_signup_password_min_length_enforced():
    with pytest.raises(ValidationError):
        SignupIn(email="a@b.com", password="1234")  # 8자 미만


def test_signup_nickname_defaults_to_email_prefix():
    body = SignupIn(email="hong@example.com", password="password123")
    assert body.nickname == "hong"


def test_signup_email_normalized_to_lowercase():
    body = SignupIn(email="  Hong@Example.COM  ", password="password123")
    assert body.email == "hong@example.com"


def test_signup_whitespace_nickname_falls_back_to_prefix():
    body = SignupIn(email="hong@example.com", password="password123", nickname="   ")
    assert body.nickname == "hong"


PROBE = """
from pydantic import ValidationError
from app.schemas import ChatRequest
try:
    ChatRequest(question="가" * 13)
except ValidationError:
    print("REJECTED")
else:
    print("ACCEPTED")
"""


def _run_probe(max_len: str) -> str:
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = {**os.environ, "MAX_QUESTION_LENGTH": max_len,
           "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
    out = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_max_question_length_env_moves_the_boundary():
    """설정과 하드코딩을 구분하는 결정 검사: 상한을 12로 낮추면 13자가 거절돼야 한다 (#53)."""
    assert _run_probe("12") == "REJECTED"
    assert _run_probe("20") == "ACCEPTED"
