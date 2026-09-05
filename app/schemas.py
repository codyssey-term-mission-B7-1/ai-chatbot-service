"""Pydantic 스키마 — 요청/응답 모델 + 입력 검증."""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── 인증 ──────────────────────────────────────────────

class SignupIn(BaseModel):
    """회원가입 요청 — 이메일 형식/비밀번호 정책(8자+) 검증."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    nickname: str = Field(default="", max_length=20, validate_default=True)

    model_config = {"json_schema_extra": {
        "examples": [
            {"email": "hong@example.com", "password": "password123", "nickname": "홍길동"},
            {"email": "kim@example.com", "password": "password123"},
        ]
    }}

    @field_validator("nickname")
    @classmethod
    def default_nickname(cls, v: str, info) -> str:
        return v.strip() or info.data.get("email", "user").split("@")[0]


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    email: str
    nickname: str


# ── 채팅 ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    """채팅 요청 — 빈 질문/공백 차단, 최대 1000자."""

    question: str = Field(min_length=1, max_length=1000)

    model_config = {"json_schema_extra": {
        "examples": [{"question": "FastAPI 배포 방법 알려줘"},
                     {"question": "내가 방금 뭘 물어봤지?"}]
    }}

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("질문을 입력해 주세요.")  # 빈 입력/공백만 있는 입력 차단
        return v


class ChatOut(BaseModel):
    answer: str
    latency_ms: int
    chat_id: int
    status: str = "success"

    model_config = {"json_schema_extra": {
        "examples": [{"answer": "직전에 'FastAPI 배포 방법'을 물어보셨고, ...",
                      "latency_ms": 1240, "chat_id": 987, "status": "success"}]
    }}


class ChatLogOut(BaseModel):
    id: int
    question: str
    answer: str
    latency_ms: int
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [{"id": 987, "question": "내가 방금 뭘 물어봤지?",
                          "answer": "직전에 'FastAPI 배포 방법'을 물어보셨고, ...",
                          "latency_ms": 1240, "status": "success",
                          "created_at": "2026-09-01T10:30:00Z"}]
        },
    }
