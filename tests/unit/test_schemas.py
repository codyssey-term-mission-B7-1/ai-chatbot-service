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
