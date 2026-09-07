"""환경설정 — 모든 민감정보는 .env에서 로딩 (코드에 직접 기입 금지)."""
import logging
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

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
        "SESSION_SECRET 이 공개된 기본값입니다 — 개발용 임시 키로 대체합니다 "
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
    ai_api_key: str | None = None          # 없으면 데모(Fake) 모드로 동작
    ai_base_url: str = "https://api.openai.com/v1/chat/completions"  # /v1까지만 적어도 됨
    ai_model: str = "gpt-4o-mini"
    ai_timeout_sec: float = 45.0           # 과제 제약: 타임아웃 필수 (기본 45초, #41)
    ai_max_retries: int = 1

    # 챗 파이프라인
    context_turns: int = 5                 # 직전 N개의 Q/A를 컨텍스트로 전달
    max_question_length: int = 1000        # 입력 검증: 길이 제한


def load_settings() -> Settings:
    """Settings 로드 + 세션 시크릿 품질 게이트 (get_settings 의 실제 배선)."""
    s = Settings()
    s.session_secret = resolve_session_secret(s.session_secret, debug=s.debug)
    return s


@lru_cache
def get_settings() -> Settings:
    return load_settings()


settings = get_settings()
