"""AI API 클라이언트 — 서버 사이드에서만 호출 (API 키 노출 방지).

- OpenAI 호환 chat completions 엔드포인트 지원: OpenAI / Groq / Novita / 코디세이 '네이토' 등
- 타임아웃/재시도/에러 매핑: Timeout → AITimeoutError(504), 그 외 → AIError(502)
- AI_API_KEY가 없으면 개발/데모용 FakeAIProvider로 동작 (테스트·로컬 데모 가능)
"""
import asyncio
import logging
from abc import ABC, abstractmethod

import httpx

from app.config import settings

logger = logging.getLogger("app.ai")

CHAT_COMPLETIONS_SUFFIX = "/chat/completions"


def normalize_endpoint(url: str) -> str:
    """엔드포인트 정규화 — 전체 URL 또는 /v1 까지 입력 가능.

    >>> normalize_endpoint("https://api.host/v1")
    'https://api.host/v1/chat/completions'
    >>> normalize_endpoint("https://api.host/v1/chat/completions")
    'https://api.host/v1/chat/completions'
    """
    url = url.strip().rstrip("/")
    if url.endswith(CHAT_COMPLETIONS_SUFFIX):
        return url
    return url + CHAT_COMPLETIONS_SUFFIX


def extract_content(data: dict) -> str:
    """OpenAI 호환 응답에서 답변 텍스트 추출 — 일부 호환 API의 변형도 지원.

    지원 형태:
      1. 표준:   choices[0].message.content = "텍스트"
      2. 배열형: choices[0].message.content = [{"type":"text","text":"..."}]
    """
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"예상과 다른 응답 형식: {str(data)[:120]}") from exc

    if isinstance(content, list):  # 멀티파트 변형
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        raise ValueError("응답 content가 비어 있어요.")
    return content


class AITimeoutError(Exception):
    """AI 호출 타임아웃."""


class AIError(Exception):
    """AI 호출 실패(네트워크/응답 오류)."""


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict]) -> str:
        """messages(chat 형식)를 받아 응답 텍스트를 반환."""


class OpenAICompatClient(AIProvider):
    def __init__(self, api_key: str, base_url: str, model: str,
                 timeout_sec: float, max_retries: int):
        self.api_key = api_key
        self.endpoint = normalize_endpoint(base_url)
        self.model = model
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries

    async def generate(self, messages: list[dict]) -> str:
        payload = {"model": self.model, "messages": messages}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_exc: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                    resp = await client.post(self.endpoint, headers=headers, json=payload)
                    resp.raise_for_status()
                    return extract_content(resp.json())
            except httpx.TimeoutException as exc:  # 타임아웃은 재시도하지 않고 즉시 매핑
                raise AITimeoutError(f"AI timeout after {self.timeout_sec}s") from exc
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                last_exc = exc
                logger.warning(
                    "event=ai_retry attempt=%d error=%s", attempt + 1, type(exc).__name__
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5)

        raise AIError(f"AI call failed: {last_exc}") from last_exc


class FakeAIProvider(AIProvider):
    """키가 없을 때 사용하는 데모 제공자 — 컨텍스트를 반영한 응답을 흉내낸다."""

    def __init__(self) -> None:
        self.last_messages: list[dict] = []  # 검증/테스트용: 마지막에 받은 messages 보관

    async def generate(self, messages: list[dict]) -> str:
        self.last_messages = messages
        await asyncio.sleep(0.05)  # 실제 호출처럼 약간의 지연
        question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        context_qs = [m["content"] for m in messages[:-1] if m["role"] == "user"]
        prefix = f"(직전 질문 인용: {context_qs[-1]!r}) " if context_qs else ""
        return (
            f"[데모 응답 — AI_API_KEY 미설정] {prefix}"
            f"질문 '{question}'에 대한 응답입니다. "
            "실제 AI 응답을 보려면 .env에 AI_API_KEY를 설정하세요."
        )


_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    """FastAPI 의존성 — 테스트에서 override 포인트."""
    global _provider
    if _provider is None:
        if settings.ai_api_key:
            _provider = OpenAICompatClient(
                api_key=settings.ai_api_key,
                base_url=settings.ai_base_url,
                model=settings.ai_model,
                timeout_sec=settings.ai_timeout_sec,
                max_retries=settings.ai_max_retries,
            )
        else:
            _provider = FakeAIProvider()
    return _provider


def reset_provider() -> None:
    """설정 변경 후 재생성용(테스트/런타임 재로드)."""
    global _provider
    _provider = None
