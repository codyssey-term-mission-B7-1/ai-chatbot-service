"""컨텍스트 구성 전략 — 같은 사용자의 직전 N개 Q/A를 프롬프트에 포함."""


def build_context(history: list[tuple[str, str]], n: int) -> list[dict]:
    """직전 n개의 (질문, 응답) 쌍을 오래된 순서대로 chat messages로 변환.

    >>> build_context([("q1","a1"),("q2","a2"),("q3","a3")], n=2)
    [{"role":"user","content":"q2"}, {"role":"assistant","content":"a2"}, ...]
    """
    recent = history[-n:] if n > 0 else []
    messages: list[dict] = []
    for q, a in recent:
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": a})
    return messages


SYSTEM_PROMPT = (
    "당신은 친절한 AI 어시스턴트입니다. "
    "이전 대화 내용을 참고하여 문맥을 유지하며 답변하세요. "
    "사용자가 '내가 방금 뭘 물어봤지?'처럼 이전 대화를 묻는다면 "
    "직전 질문과 답변을 인용해 알려주세요."
)
