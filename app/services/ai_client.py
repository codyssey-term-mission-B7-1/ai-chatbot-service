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
    """전체 엔드포인트 또는 /v1만 입력할 수 있다. 중복 접미사는 정리한다."""
    url = url.strip().rstrip("/")
    suffix = CHAT_COMPLETIONS_SUFFIX
    while url.endswith(suffix):
        url = url[: -len(suffix)].rstrip("/")
    return url + suffix


def extract_content(data: dict) -> str:
    """문자열/텍스트 multipart만 수용한다. 잘못된 응답은 민감 원문 없이 ValueError.

    finish_reason=length(응답이 max_tokens로 잘림)에는 말줄임 표식을 붙여
    사용자에게 응답이 끊겼음을 알린다(종전에는 조용히 잘린 문자열을 돌려주어
    다음 문맥이 오염될 수 있었음).
    """
    try:
        choice = data["choices"][0]
        message = choice["message"]
        finish = str(choice.get("finish_reason") or "")
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("AI 응답의 choices/message/content 형식이 올바르지 않습니다.") from exc
    content = message.get("content", "")
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
    if finish == "length":
        content = content.rstrip() + " …(응답이 길이 제한으로 잘렸어요)"
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
        # 전체 예산 안에서 개별 시도(연결+읽기)의 시간 상한을 둔다.
        # 재시도 대기(0.5s)까지 포함한 전체 상한은 바깥 asyncio.timeout이 보장한다.
        self._per_attempt_timeout = httpx.Timeout(
            connect=min(10.0, timeout_sec),
            read=timeout_sec,
            write=min(10.0, timeout_sec),
            pool=min(5.0, timeout_sec),
        )

    def build_payload(self, messages: list[dict]) -> dict:
        """요청 본문 — 응답 길이·온도를 서버 정책으로 고정(미설정 시 제공사 기본값 노출 방지)."""
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": settings.ai_max_tokens,
            "temperature": settings.ai_temperature,
        }

    async def generate(self, messages: list[dict]) -> str:
        # 전체 시간 예산은 이 바깥 타임아웃이 1회만 보장한다. httpx 내부 timeout과 이중으로
        # 걸지 않음 — 이중 설정 시 재시도 경로에서 예산이 누적되어 상한을 깨뜨릴 수 있다.
        try:
            async with asyncio.timeout(self.timeout_sec):
                return await self._attempts(messages)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise AITimeoutError("AI 호출 시간 예산을 초과했습니다.") from exc

    async def _attempts(self, messages: list[dict]) -> str:
        payload = self.build_payload(messages)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        # 연결 풀·HTTP/2 유지로 단기 다중 요청(TCP 핸드셰이크) 비용을 줄인다.
        async with httpx.AsyncClient(
            timeout=self._per_attempt_timeout,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
        ) as client:
            previous_error = ""
            for attempt in range(self.max_retries + 1):
                if attempt > 0:
                    # 대기 중 전체 예산이 끝나면 바깥 asyncio.timeout이 캔슬시킨다
                    # → 재시도를 "실제로 시작하지 않은" 것으로 취급한다.
                    # 그래서 ai_retry 이벤트는 sleep *후*에 기록한다(테스트가 이 의미를 고정).
                    await asyncio.sleep(0.5)
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
                    raise  # 시간 초과는 재시도하지 않는다(전체 예산을 바깥에서 이미 소진 중).
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
