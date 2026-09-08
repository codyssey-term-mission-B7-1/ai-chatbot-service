"""Unicode·설정 경계 계약."""

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas import ChatRequest, SignupIn


def test_501_emoji_is_501_codepoints_and_is_accepted():
    assert len(ChatRequest(question="🙂" * 501).question) == 501


def test_question_trims_before_length_validation():
    assert ChatRequest(question=" " * 1000 + "내용" + " " * 1000).question == "내용"


def test_invalid_password_unicode_is_validation_error():
    with pytest.raises(ValidationError):
        SignupIn(email="unicode@example.com", password="\ud800" * 8)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"context_turns": -1},
        {"context_turns": 201},
        {"ai_timeout_sec": 0},
        {"ai_max_retries": -1},
        {"max_question_length": 0},
    ],
)
def test_configuration_rejects_unusable_limits(kwargs):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)
