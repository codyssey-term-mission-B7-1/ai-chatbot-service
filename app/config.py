"""환경설정 — 실제 비밀값은 .env 파일 또는 프로세스 환경변수에서 로딩 (코드에 직접 기입 금지)."""

import logging
import secrets
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.policies import MAX_CONTEXT_TURNS

logger = logging.getLogger(__name__)

# 세션 서명 키 품질 기준 — 공개된 예시 값이나 짧은 키로는 쿠키를 위조할 수 있다.
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 앱
    app_name: str = "AI Chatbot Service"
    debug: bool = False

    # DB (SQLite 권장)
    database_url: str = "sqlite:///./app.db"

    # 세션
    session_secret: str = "dev-secret-change-me"  # 운영: .env에서 반드시 변경

    # AI (OpenAI 호환 chat completions — OpenAI/Groq/코디세이 네이토 등)
    ai_api_key: str | None = None  # 없으면 데모(Fake) 모드로 동작
    ai_base_url: str = "https://api.openai.com/v1/chat/completions"  # /v1까지만 적어도 됨
    ai_model: str = "gpt-4o-mini"
    ai_timeout_sec: float = Field(default=45.0, gt=0)  # AI 호출 전체 예산, 초
    ai_max_retries: int = Field(default=1, ge=0, le=5)

    # 챗 파이프라인
    context_turns: int = Field(default=5, ge=0, le=MAX_CONTEXT_TURNS)  # 0이면 문맥 비활성화
    max_question_length: int = Field(default=1000, ge=1, le=100000)  # 입력 검증: 길이 제한

    # 로그인 무차별 대입 방어(#72) — 이메일별 실패 누적 잠금. 프로세스 메모리·단일 워커 전제
    login_max_fails: int = Field(default=5, ge=1)
    login_lockout_sec: float = Field(default=900, gt=0)


def load_settings() -> Settings:
    """설정을 불러온 뒤 세션 서명 키를 검증한다. get_settings에서 실제로 호출된다."""
    s = Settings()
    s.session_secret = resolve_session_secret(s.session_secret, debug=s.debug)
    return s


@lru_cache
def get_settings() -> Settings:
    return load_settings()


settings = get_settings()
