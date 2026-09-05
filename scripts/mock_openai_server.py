#!/usr/bin/env python3
"""네이토(OpenAI 호환) 목업 서버 — 실제 API 키 없이 로컬에서 E2E 검증용.

코디세이 '네이토'처럼 OpenAI chat completions 형식을 반환하는 가짜 서버.
실제 키 받기 전 단계(D1~D4)에 파이프라인을 미리 검증할 때 사용한다.

실행:  python scripts/mock_openai_server.py   → http://0.0.0.0:8001
연결:  .env 에 아래처럼 설정
       AI_API_KEY=anything
       AI_BASE_URL=http://127.0.0.1:8001/v1
       AI_MODEL=neito-1

시나리오 트리거 (마지막 질문에 포함되면):
  - "천천히" → 30초 지연 (타임아웃/504 시나리오 테스트용)
  - "방금"   → 직전 질문을 인용하는 문맥 응답
  - 그 외    → 일반 응답 (컨텍스트 반영 개수 표시)
"""
import asyncio
import time
import uuid

from fastapi import FastAPI

app = FastAPI(title="Mock OpenAI-Compatible API (네이토 시뮬레이터)")


@app.get("/health")
async def health():
    return {"status": "ok", "mock": True}


@app.get("/v1/models")
async def list_models():
    return {"object": "list", "data": [{"id": "neito-1", "object": "model", "owned_by": "codisy"}]}


@app.post("/v1/chat/completions")
async def chat_completions(payload: dict):
    messages = payload.get("messages", [])
    users = [m.get("content", "") for m in messages if m.get("role") == "user"]
    question = users[-1] if users else ""
    model = payload.get("model", "neito-1")

    if "천천히" in question:
        await asyncio.sleep(30)  # 타임아웃 유발 (클라이언트 타임아웃 < 30s)

    if "방금" in question and len(users) >= 2:
        prev = users[-2]
        content = (
            f"직전에 '{prev}'을(를) 물어보셨어요. "
            "그때 드린 답변을 바탕으로 이어서 설명드릴게요. (네이토 mock 문맥 응답)"
        )
    else:
        content = (
            f"[네이토 mock 응답] '{question}'에 대한 답변입니다. "
            f"(model={model}, 컨텍스트 {max(len(users) - 1, 0)}건 반영)"
        )

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46},
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
