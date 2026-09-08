"""AI 시간 예산·재시도·응답 형식 정책. 외부 AI를 호출하지 않는다."""

import asyncio
import logging
import time

import httpx
import pytest

from app.services.ai_client import AIError, AITimeoutError, OpenAICompatClient, extract_content


@pytest.mark.parametrize("value", [None, 12, {"value": "x"}, ["x"]])
def test_multipart_text_must_be_a_string(value):
    with pytest.raises(ValueError):
        extract_content({"choices": [{"message": {"content": [{"type": "text", "text": value}]}}]})


def test_invalid_unicode_response_is_a_format_error():
    with pytest.raises(ValueError):
        extract_content({"choices": [{"message": {"content": "\ud800"}}]})


@pytest.mark.parametrize(("retries", "attempts", "events"), [(0, 1, 0), (1, 2, 1), (2, 3, 2)])
def test_retry_event_counts_started_additional_attempts(
    monkeypatch, caplog, retries, attempts, events
):
    calls = []

    async def fail(self, *args, **kwargs):
        calls.append(1)
        raise httpx.ConnectError("synthetic")

    async def no_delay(delay):
        return None

    monkeypatch.setattr(httpx.AsyncClient, "post", fail)
    monkeypatch.setattr(asyncio, "sleep", no_delay)
    with caplog.at_level(logging.WARNING), pytest.raises(AIError):
        asyncio.run(
            OpenAICompatClient("fake", "https://example.test/v1", "test", 3, retries).generate([])
        )
    assert len(calls) == attempts
    assert sum("event=ai_retry" in r.message for r in caplog.records) == events


def test_authentication_error_is_not_retried(monkeypatch, caplog):
    calls = []

    async def fail(self, *args, **kwargs):
        calls.append(1)
        return httpx.Response(401, request=httpx.Request("POST", "https://example.test"))

    monkeypatch.setattr(httpx.AsyncClient, "post", fail)
    with caplog.at_level(logging.WARNING), pytest.raises(AIError):
        asyncio.run(
            OpenAICompatClient("fake", "https://example.test/v1", "test", 3, 2).generate([])
        )
    assert len(calls) == 1
    assert not any("event=ai_retry" in r.message for r in caplog.records)


def test_total_budget_includes_backoff_and_does_not_claim_an_unstarted_retry(monkeypatch, caplog):
    calls = []

    async def fail(self, *args, **kwargs):
        calls.append(1)
        raise httpx.ConnectError("synthetic")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail)
    start = time.monotonic()
    with caplog.at_level(logging.WARNING), pytest.raises(AITimeoutError):
        asyncio.run(
            OpenAICompatClient("fake", "https://example.test/v1", "test", 0.1, 1).generate([])
        )
    assert time.monotonic() - start < 1.0
    assert len(calls) == 1
    assert not any("event=ai_retry" in r.message for r in caplog.records)


def test_total_budget_wraps_whole_generate(monkeypatch):
    async def slow(self, *args, **kwargs):
        await asyncio.sleep(0.5)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "late"}}]},
            request=httpx.Request("POST", "https://example.test"),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", slow)
    with pytest.raises(AITimeoutError):
        asyncio.run(
            OpenAICompatClient("fake", "https://example.test/v1", "test", 0.1, 0).generate([])
        )
