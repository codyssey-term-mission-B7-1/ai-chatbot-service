"""환경설정 — 모든 민감정보는 .env에서 로딩 (코드에 직접 기입 금지)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    ai_timeout_sec: float = 10.0           # 과제 제약: 타임아웃 필수
    ai_max_retries: int = 1

    # 챗 파이프라인
    context_turns: int = 5                 # 직전 N개의 Q/A를 컨텍스트로 전달
    max_question_length: int = 1000        # 입력 검증: 길이 제한


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
