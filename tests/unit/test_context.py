"""유닛 테스트 — 컨텍스트 빌더 (최근 N개 Q/A 전략)."""
from app.services.context import build_context


def test_context_returns_only_last_n_pairs():
    history = [(f"q{i}", f"a{i}") for i in range(1, 11)]  # 10개
    ctx = build_context(history, n=3)
    assert len(ctx) == 6  # Q/A 쌍 3개 → 메시지 6개
    assert ctx[0] == {"role": "user", "content": "q8"}       # 최신 3개만
    assert ctx[-1] == {"role": "assistant", "content": "a10"}
    assert [m["content"] for m in ctx if m["role"] == "user"] == ["q8", "q9", "q10"]


def test_context_preserves_oldest_first_order():
    history = [("q1", "a1"), ("q2", "a2")]
    ctx = build_context(history, n=5)  # n이 더 길어도 전체, 오래된 순서 유지
    assert ctx[0]["content"] == "q1"


def test_context_with_empty_history_returns_empty():
    assert build_context([], n=5) == []
