"""환경설정 — 실제 비밀값은 .env 파일 또는 프로세스 환경변수에서 로딩 (코드에 직접 기입 금지)."""

import logging
import secrets
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.policies import MAX_CONTEXT_TURNS, QUESTION_ABS_MAX_CHARS

logger = logging.getLogger(__name__)

MIN_SECRET_LEN = 32
INSECURE_SECRETS = {
    "change-me",
    "change-me-to-random-string",
    "dev-secret-change-me",
    "secret",
    "changeme",
    "your-secret-key",
}


def resolve_session_secret(secret: str, *, debug: bool) -> str:
    """운영(debug=False)에서 약한 SESSION_SECRET을 거부하고, 개발에서는 임시 키로 대체한다."""
    if secret not in INSECURE_SECRETS and len(secret) >= MIN_SECRET_LEN:
        return secret
    if not debug:
        raise RuntimeError(
            "SESSION_SECRET 이 안전하지 않아요. 공개된 기본값이거나 "
            f"{MIN_SECRET_LEN}자 미만입니다.\n"
            '  발급: python -c "import secrets; print(secrets.token_hex(32))"\n'
            "  로컬 개발에서는 .env 에 DEBUG=true 를 켜면 임시 키로 자동 대체됩니다."
        )
    logger.warning(
        "SESSION_SECRET 이 공개된 예시 값이거나 최소 길이에 미달하여 개발용 임시 키로 대체합니다 "
        "(재시작 시 세션 초기화). 운영에서는 .env에 %d자 이상 무작위 값을 설정하세요.",
        MIN_SECRET_LEN,
    )
    return secrets.token_hex(32)


def resolve_password_pepper(pepper: str, *, debug: bool) -> str:
    """비밀번호 페퍼(#보안 강화) — 운영에서 미설정/약한 값은 거부, 개발은 임시 페퍼로 대체."""
    if pepper and pepper not in INSECURE_SECRETS and len(pepper) >= MIN_SECRET_LEN:
        return pepper
    if not debug:
        raise RuntimeError(
            "PASSWORD_PEPPER 가 안전하지 않아요. 비어 있거나 공개된 기본값이거나 "
            f"{MIN_SECRET_LEN}자 미만입니다.\n"
            '  발급: python -c "import secrets; print(secrets.token_hex(32))"\n'
            "  로컬 개발에서는 .env 에 DEBUG=true 를 켜면 임시 페퍼로 자동 대체됩니다."
        )
    logger.warning(
        "PASSWORD_PEPPER 가 비어 있거나 최소 길이에 미달하여 개발용 임시 페퍼로 대체합니다 "
        "(재시작 시 기존 페퍼 해시와 호환되지 않음). "
        "운영에서는 .env에 %d자 이상 무작위 값을 설정하세요.",
        MIN_SECRET_LEN,
    )
    return secrets.token_hex(32)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Chatbot Service"
    debug: bool = False
    build_sha: str = ""

    database_url: str = "sqlite:///./app.db"

    session_secret: str = "dev-secret-change-me"
    password_pepper: str = ""
    session_max_age_hours: int = Field(default=24, ge=1, le=168)

    ai_api_key: str | None = None
    ai_base_url: str = "https://api.openai.com/v1/chat/completions"
    ai_model: str = "gpt-4o-mini"
    ai_timeout_sec: float = Field(default=45.0, gt=0)
    ai_max_retries: int = Field(default=1, ge=0, le=5)
    ai_max_tokens: int = Field(default=800, ge=16, le=8192)
    ai_temperature: float = Field(default=0.6, ge=0, le=2)

    docs_enabled: bool = True

    max_request_body_bytes: int = Field(default=1_048_576, ge=0)

    context_turns: int = Field(default=5, ge=0, le=MAX_CONTEXT_TURNS)
    max_question_length: int = Field(default=1000, ge=1, le=QUESTION_ABS_MAX_CHARS)
    max_threads_per_user: int = Field(default=100, ge=1)

    login_max_fails: int = Field(default=5, ge=1)
    login_lockout_sec: float = Field(default=900, gt=0)

    chat_rate_per_min: int = Field(default=10, ge=0)

    signup_rate_per_ip_per_min: int = Field(default=5, ge=0)

    password_reset_rate_per_ip_per_min: int = Field(default=5, ge=0)

    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "AI Chatbot Service <no-reply@example.com>"

    resend_api_key: str = ""
    resend_from: str = "onboarding@resend.dev"
    password_reset_expiry_minutes: int = Field(default=30, ge=5, le=1440)
    password_reset_max_requests: int = Field(default=3, ge=1)
    password_reset_window_minutes: int = Field(default=15, ge=1)


def load_settings() -> Settings:
    """설정을 불러온 뒤 세션 서명 키를 검증한다. get_settings에서 실제로 호출된다."""
    s = Settings()
    s.session_secret = resolve_session_secret(s.session_secret, debug=s.debug)
    s.password_pepper = resolve_password_pepper(s.password_pepper, debug=s.debug)
    return s


@lru_cache
def get_settings() -> Settings:
    return load_settings()


settings = get_settings()
