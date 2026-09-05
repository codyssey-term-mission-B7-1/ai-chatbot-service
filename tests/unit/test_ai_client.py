"""유닛 테스트 — AI 클라이언트 (엔드포인트 정규화 / 응답 파싱 / 에러 매핑)."""
import asyncio

import httpx
import pytest

from app.services.ai_client import (
    AIError,
    AITimeoutError,
    OpenAICompatClient,
    extract_content,
    normalize_endpoint,
)


# ── 엔드포인트 정규화 ──────────────────────────────

def test_normalize_endpoint_accepts_full_url():
    url = "https://api.codisy.example/v1/chat/completions"
    assert normalize_endpoint(url) == url


def test_normalize_endpoint_appends_to_v1_base():
    assert normalize_endpoint("https://api.codisy.example/v1") == \
        "https://api.codisy.example/v1/chat/completions"


def test_normalize_endpoint_strips_trailing_slash():
    assert normalize_endpoint("https://host/v1/") == "https://host/v1/chat/completions"


# ── 응답 파싱 (호환 API 변형 대응) ────────────────

def test_extract_content_standard_format():
    data = {"choices": [{"message": {"role": "assistant", "content": "안녕!"}}]}
    assert extract_content(data) == "안녕!"


def test_extract_content_multipart_list_format():
    data = {"choices": [{"message": {"content": [
        {"type": "text", "text": "첫 번째 "}, {"type": "text", "text": "두 번째"},
    ]}}]}
    assert extract_content(data) == "첫 번째 두 번째"


def test_extract_content_invalid_shape_raises():
    with pytest.raises(ValueError):
        extract_content({"unexpected": "shape"})


def test_extract_content_empty_string_raises():
    with pytest.raises(ValueError):
        extract_content({"choices": [{"message": {"content": "   "}}]})


# ── 에러 매핑 ─────────────────────────────────────

def _client(timeout_sec=0.001, max_retries=0):
    return OpenAICompatClient(
        api_key="test-key", base_url="https://example.test/v1",
        model="test-model", timeout_sec=timeout_sec, max_retries=max_retries,
    )


def test_timeout_exception_maps_to_ai_timeout_error(monkeypatch):
    async def fake_post(self, *args, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(AITimeoutError):
        asyncio.run(_client().generate([{"role": "user", "content": "hi"}]))


def test_http_error_maps_to_ai_error(monkeypatch):
    async def fake_post(self, *args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(AIError):
        asyncio.run(_client().generate([{"role": "user", "content": "hi"}]))
