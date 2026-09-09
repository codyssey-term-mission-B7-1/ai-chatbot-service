"""Pydantic 요청/응답 계약. 문자 수=Unicode 코드 포인트, 응답 시각=UTC."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.config import settings
from app.policies import MAX_NICKNAME_CHARS, MAX_PASSWORD_BYTES, MAX_PASSWORD_CHARS


class SignupIn(BaseModel):
    """8~64 코드 포인트와 bcrypt의 UTF-8 72바이트 한계를 모두 검증한다."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_CHARS)
    nickname: str = Field(default="", max_length=MAX_NICKNAME_CHARS, validate_default=True)
    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {"email": "hong@example.com", "password": "password123", "nickname": "홍길동"},
                {"email": "kim@example.com", "password": "password123"},
            ]
        },
    }

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("비밀번호는 공백만으로 구성될 수 없어요.")
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError("비밀번호는 UTF-8 기준 72바이트 이하여야 합니다.")
        return value

    @field_validator("nickname", mode="before")
    @classmethod
    def nickname_text(cls, value):
        if isinstance(value, str):
            value.encode("utf-8")
            return value.strip()
        return value

    @field_validator("nickname")
    @classmethod
    def default_nickname(cls, value: str, info) -> str:
        return (value.strip() or info.data.get("email", "user").split("@")[0])[:MAX_NICKNAME_CHARS]


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class PasswordResetRequestIn(BaseModel):
    """재설정 요청 — 응답은 계정 존재 여부를 누출하지 않는다."""

    email: EmailStr
    model_config = {"extra": "forbid"}


class PasswordResetCompleteIn(BaseModel):
    """재설정 완료 — 토큰과 새 비밀번호(회원가입과 동일한 정책)."""

    token: str = Field(min_length=20, max_length=128)
    new_password: str = Field(min_length=8, max_length=MAX_PASSWORD_CHARS)
    model_config = {"extra": "forbid"}

    @field_validator("new_password")
    @classmethod
    def new_password_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("비밀번호는 공백만으로 구성될 수 없어요.")
        return value


class UserOut(BaseModel):
    email: str
    nickname: str
    is_admin: bool = False


class ChatRequest(BaseModel):
    """공백 질문 거부, 상한은 MAX_QUESTION_LENGTH(기본 1000 코드 포인트)."""

    question: str = Field(min_length=1, max_length=settings.max_question_length)
    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {"question": "FastAPI 배포 방법 알려줘"},
                {"question": "내가 방금 뭘 물어봤지?"},
            ]
        },
    }

    @field_validator("question", mode="before")
    @classmethod
    def not_blank(cls, value):
        if isinstance(value, str):
            value.encode("utf-8")
            value = value.strip()
            if not value:
                raise ValueError("질문을 입력해 주세요.")
        return value


class ChatOut(BaseModel):
    answer: str
    latency_ms: int
    chat_id: int
    status: str = "success"
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "answer": "직전에 'FastAPI 배포 방법'을 물어보셨어요.",
                    "latency_ms": 1240,
                    "chat_id": 987,
                    "status": "success",
                },
            ]
        }
    }


class ChatLogOut(BaseModel):
    id: int
    question: str
    answer: str
    latency_ms: int
    status: str
    request_id: str = ""
    created_at: datetime
    model_config = {"from_attributes": True}

    @field_validator("created_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        # 앱이 UTC로 저장한 SQLite datetime은 조회 시 tzinfo가 사라진다.
        # 외부 DB/수동 이관 값도 UTC라는 계약은 별도로 지켜야 한다.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class AdminChatLogOut(ChatLogOut):
    user_id: int


class AdminLogPage(BaseModel):
    items: list[AdminChatLogOut]
    next_before_id: int | None = None


LogStatus = Literal["success", "ai_error"]


class PasswordHashStatusOut(BaseModel):
    """페퍼 해시 마이그레이션 현황 — legacy가 0이면 레거시 폴백 제거 가능."""

    total: int
    peppered: int
    legacy: int


class DeletedUserOut(BaseModel):
    user_id: int
    email: str
