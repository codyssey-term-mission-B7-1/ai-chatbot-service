#!/usr/bin/env python3
"""CONTEXT_TURNS 값 실험 (#7) — 문자량과 문맥 범위 측정 (요금·실 AI 품질 측정 아님).

실제 /api/chat 파이프라인을 태우고, AI에 전달된 messages를 그대로 캡처해
N=3/5/10에서 프롬프트 크기와 문맥 커버리지가 어떻게 달라지는지 잰다.

실행: python scripts/experiment_context_turns.py
"""
import logging
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"  # 이 프로세스는 항상 격리 메모리 DB만 사용
os.environ["AI_API_KEY"] = ""  # 실 AI 호출 금지
os.environ.setdefault("DEBUG", "true")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.ai_client import get_ai_provider  # noqa: E402


TOTAL_TURNS = 12          # 실험용으로 쌓는 대화 턴 수
ANSWER_LENGTH = 300       # 실험 가정값(문자). 실제 토큰 수·답변 품질·요금은 측정하지 않는다.
CANDIDATES = [3, 5, 10]


class CapturingProvider:
    """AI 호출을 가로채 전달된 messages를 보관하는 페이크."""

    def __init__(self) -> None:
        self.last_messages: list[dict] = []

    async def generate(self, messages: list[dict]) -> str:
        self.last_messages = messages
        return "답" * ANSWER_LENGTH


def measure(n: int) -> dict:
    """CONTEXT_TURNS=n 으로 TOTAL_TURNS만큼 대화한 뒤 마지막 프롬프트를 측정."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    provider = CapturingProvider()

    def _get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    old_overrides = dict(app.dependency_overrides)
    old_turns = settings.context_turns
    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_db] = _get_db
    settings.context_turns = n

    try:
        with TestClient(app, base_url="https://testserver") as c:
            c.post("/api/auth/signup", json={"email": f"exp{n}@example.com",
                                             "password": "Test1234!"})
            c.post("/api/auth/login", json={"email": f"exp{n}@example.com",
                                            "password": "Test1234!"})
            for i in range(1, TOTAL_TURNS + 1):
                c.post("/api/chat", json={"question": f"{i}번째 질문입니다"})
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
        settings.context_turns = old_turns
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    msgs = provider.last_messages
    chars = sum(len(m["content"]) for m in msgs)
    past_qs = [m["content"] for m in msgs[1:-1] if m["role"] == "user"]
    oldest = past_qs[0].split("번째")[0] if past_qs else "-"
    return {
        "n": n,
        "messages": len(msgs),
        "past_pairs": len(past_qs),
        "chars": chars,
        "oldest_turn": oldest,
    }


def main() -> None:
    original = settings.context_turns
    old_log_disable = logging.root.manager.disable
    logging.disable(logging.INFO)
    print(f"LOCAL/FAKE 실험: {TOTAL_TURNS}번째 요청의 프롬프트 측정 "
          f"(답변 길이 {ANSWER_LENGTH}자 가정)\n")
    header = (f"{'N':>3}  {'메시지 수':>9}  {'과거 Q/A':>8}  "
              f"{'프롬프트 문자':>13}  {'가장 오래된 턴':>14}")
    print(header)
    print("-" * len(header))
    rows = []
    try:
        for n in CANDIDATES:
            r = measure(n)
            rows.append(r)
            print(f"{r['n']:>3}  {r['messages']:>9}  {r['past_pairs']:>8}  "
                  f"{r['chars']:>13,}  {r['oldest_turn']:>14}번째")
    finally:
        settings.context_turns = original
        logging.disable(old_log_disable)

    base = rows[0]["chars"]
    print()
    for r in rows:
        print(f"  N={r['n']:>2}: 프롬프트 {r['chars']:,}자 (N=3 대비 {r['chars'] / base:.1f}배), "
              f"직전 {r['past_pairs']}턴까지 기억")


if __name__ == "__main__":
    main()
