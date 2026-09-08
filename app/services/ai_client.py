"""서버 전용 OpenAI 호환 클라이언트.

AI_TIMEOUT_SEC는 한 generate 호출의 전체 예산(연결·읽기·재시도·대기 포함).
타임아웃/응답 형식 오류/429 외 4xx는 재시도하지 않는다.
전송 오류·429·5xx만 AI_MAX_RETRIES 횟수만큼 추가 시도한다.
키가 없을 때의 Fake는 설정에 따른 데모이며 실제 AI 실패 시 폴백이 아니다.
"""

import asyncio
import logging
from abc import ABC, abstractmethod

import httpx

from app.config import settings
from app.logging_config import log_event

logger = logging.getLogger("app.ai")
CHAT_COMPLETIONS_SUFFIX = "/chat/completions"


def normalize_endpoint(url: str) -> str:
    """전체 엔드포인트 또는 /v1까지 입력할 수 있다."""
    url = url.strip().rstrip("/")
    return url if url.endswith(CHAT_COMPLETIONS_SUFFIX) else url + CHAT_COMPLETIONS_SUFFIX


def extract_content(data: dict) -> str:
    """문자열/텍스트 multipart만 수용한다. 잘못된 응답은 민감 원문 없이 ValueError."""
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("AI 응답의 choices/message/content 형식이 올바르지 않습니다.") from exc
    if isinstance(content, list):
        pieces = []
        for part in content:
            if not isinstance(part, dict):
                raise ValueError("AI multipart 응답 항목은 객체여야 합니다.")
            if "text" not in part:
                continue  # 텍스트가 아닌 부가 항목은 응답 텍스트에서 제외
            if not isinstance(part["text"], str):
                raise ValueError("AI multipart 응답의 text는 문자열이어야 합니다.")
            pieces.append(part["text"])
        content = "".join(pieces)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("AI 응답 content가 비어 있거나 문자열이 아닙니다.")
    try:
        content.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("AI 응답이 유효한 UTF-8 텍스트가 아닙니다.") from exc
    return content


class AITimeoutError(Exception):
    """AI 호출 전체 시간 예산 초과 또는 I/O 타임아웃."""


class AIError(Exception):
    """타임아웃 이외의 AI 호출·응답 오류. HTTP 계층에서 502로 매핑."""


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict]) -> str:
        """chat messages를 받아 응답 텍스트 반환."""


class OpenAICompatClient(AIProvider):
    def __init__(
        self, api_key: str, base_url: str, model: str, timeout_sec: float, max_retries: int
    ):
        if timeout_sec <= 0 or max_retries < 0:
            raise ValueError("시간 예산은 양수, 추가 시도 횟수는 0 이상이어야 합니다.")
        self.api_key = api_key
        self.endpoint = normalize_endpoint(base_url)
        self.model = model
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries

    async def generate(self, messages: list[dict]) -> str:
        try:
            async with asyncio.timeout(self.timeout_sec):
                return await self._attempts(messages)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise AITimeoutError("AI 호출 시간 예산을 초과했습니다.") from exc

    async def _attempts(self, messages: list[dict]) -> str:
        payload = {"model": self.model, "messages": messages}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            previous_error = ""
            for attempt in range(self.max_retries + 1):
                if attempt > 0:
                    log_event(
                        logger,
                        "ai_retry",
                        level=logging.WARNING,
                        attempt=attempt + 1,
                        previous_error=previous_error,
                        delay_ms=500,
                    )
                try:
                    response = await client.post(self.endpoint, headers=headers, json=payload)
                    response.raise_for_status()
                    return extract_content(response.json())
                except httpx.TimeoutException:
                    raise  # 시간 초과는 재시도하지 않는다.
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    raise AIError("AI 응답 형식 오류") from exc
                except httpx.HTTPError as exc:
                    retryable = (
                        not isinstance(exc, httpx.HTTPStatusError)
                        or exc.response.status_code == 429
                        or exc.response.status_code >= 500
                    )
                    if not retryable or attempt >= self.max_retries:
                        raise AIError("AI 호출 실패: " + type(exc).__name__) from exc
                    previous_error = type(exc).__name__
                    # 대기 중 전체 예산이 끝나면 다음 반복/ai_retry 기록에 도달하지 않는다.
                    await asyncio.sleep(0.5)
        raise AIError("AI 호출이 완료되지 않았습니다.")


class FakeAIProvider(AIProvider):
    """키가 없는 로컬 데모용. 실 AI 연결·품질 검증 증거로 사용하면 안 된다."""

    def __init__(self) -> None:
        self.last_messages: list[dict] = []

    async def generate(self, messages: list[dict]) -> str:
        self.last_messages = messages
        await asyncio.sleep(0.05)
        question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        context_qs = [m["content"] for m in messages[:-1] if m["role"] == "user"]
        prefix = f"(직전 질문 인용: {context_qs[-1]!r}) " if context_qs else ""
        return (
            f"[데모 응답 — AI_API_KEY 미설정] {prefix}질문 '{question}'에 대한 응답입니다. "
            "실제 AI 연결은 별도 검증해야 합니다."
        )


_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    global _provider
    if _provider is None:
        _provider = (
            OpenAICompatClient(
                settings.ai_api_key,
                settings.ai_base_url,
                settings.ai_model,
                settings.ai_timeout_sec,
                settings.ai_max_retries,
            )
            if settings.ai_api_key
            else FakeAIProvider()
        )
    return _provider


def reset_provider() -> None:
    """현재 settings 객체로 provider만 재생성. .env를 다시 읽는 함수는 아니다."""
    global _provider
    _provider = None
