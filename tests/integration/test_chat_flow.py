"""통합 테스트 — 챗 파이프라인 전체 흐름 + 타임아웃 생존성 + 문맥 유지."""
import httpx

from tests.conftest import signup_and_login


def test_chat_blocked_without_login(client):
    """접근 제어: 비로그인 사용자는 채팅 불가."""
    r = client.post("/api/chat", json={"question": "안녕"})
    assert r.status_code == 401


def test_empty_question_rejected_by_validation(client):
    signup_and_login(client)
    r = client.post("/api/chat", json={"question": "   "})
    assert r.status_code == 422  # Pydantic 입력 검증


def test_full_chat_pipeline_saves_log(client, fake_ai):
    """가입 → 로그인 → 질문 → AI 응답 → DB 저장 → 내 로그 조회 전체 흐름."""
    signup_and_login(client)

    r = client.post("/api/chat", json={"question": "배포 방법 알려줘"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "테스트 응답입니다."
    assert body["chat_id"] > 0
    assert body["latency_ms"] >= 0

    logs = client.get("/api/me/chats").json()
    assert len(logs) == 1
    assert logs[0]["question"] == "배포 방법 알려줘"
    assert logs[0]["answer"] == "테스트 응답입니다."
    assert logs[0]["status"] == "success"
    assert "created_at" in logs[0]  # 최소 추적 필드: 생성 시각


def test_timeout_returns_504_and_server_survives(client, fake_ai):
    """타임아웃 강제 유발 → 504 안내 + 서버 생존 + 실패 로그 저장."""
    fake_ai.error = httpx.TimeoutException("timeout")
    signup_and_login(client)

    r = client.post("/api/chat", json={"question": "긴 글 요약해줘"})
    assert r.status_code == 504
    assert "AI_TIMEOUT" in r.json()["detail"]

    # 서버 비정상 종료 없음
    assert client.get("/health").status_code == 200

    # 실패도 추적 대상으로 DB에 기록됨 (status=ai_error)
    logs = client.get("/api/me/chats").json()
    assert len(logs) == 1 and logs[0]["status"] == "ai_error"


def test_context_carries_previous_qa(client, fake_ai):
    """문맥 유지: 직전 질문이 다음 AI 호출의 프롬프트에 포함됨."""
    signup_and_login(client)
    client.post("/api/chat", json={"question": "오늘 날씨 어때?"})
    client.post("/api/chat", json={"question": "내가 방금 뭘 물어봤지?"})

    sent = [m["content"] for m in fake_ai.last_messages]
    assert "오늘 날씨 어때?" in sent  # 직전 Q/A가 컨텍스트로 전달됨


def test_my_chats_isolated_per_user(client, fake_ai):
    """사용자 기준 추적: 다른 사용자의 로그는 보이지 않음."""
    signup_and_login(client, email="one@test.com")
    client.post("/api/chat", json={"question": "1번 사용자 질문"})

    signup_and_login(client, email="two@test.com")
    client.post("/api/chat", json={"question": "2번 사용자 질문"})

    logs = client.get("/api/me/chats").json()
    assert [log["question"] for log in logs] == ["2번 사용자 질문"]  # 마지막 로그인 사용자 것만
