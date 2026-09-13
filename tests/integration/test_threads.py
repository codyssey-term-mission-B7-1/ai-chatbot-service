"""통합 테스트 — 대화 스레드(새 채팅): 생성·목록·삭제·격리·스레드 단위 문맥."""

from app.config import settings
from tests.conftest import signup_and_login


def test_thread_requires_login(client):
    assert client.post("/api/threads").status_code == 401
    assert client.get("/api/threads").status_code == 401
    assert client.delete("/api/threads/1").status_code == 401


def test_create_and_list_thread(client):
    signup_and_login(client)
    # 신규 사용자의 목록은 비어 있다(기본 대화는 첫 채팅에서 생성)
    assert client.get("/api/threads").json() == []

    r = client.post("/api/threads")
    assert r.status_code == 201
    body = r.json()
    assert body["id"] > 0
    assert body["title"] is None
    assert body["created_at"].endswith("Z")
    assert "updated_at" in body

    threads = client.get("/api/threads").json()
    assert len(threads) == 1 and threads[0]["id"] == body["id"]


def test_default_thread_created_on_first_chat(client, fake_ai):
    signup_and_login(client)
    r = client.post("/api/chat", json={"question": "첫 질문"})
    assert r.status_code == 200

    threads = client.get("/api/threads").json()
    assert len(threads) == 1
    assert threads[0]["title"] == "기본 대화"

    logs = client.get("/api/me/chats").json()
    assert len(logs) == 1 and logs[0]["thread_id"] == threads[0]["id"]


def test_thread_list_isolated_per_user(client):
    signup_and_login(client, email="one@test.com")
    client.post("/api/threads")
    mine = client.get("/api/threads").json()
    assert len(mine) == 1

    signup_and_login(client, email="two@test.com")
    assert client.get("/api/threads").json() == []


def test_delete_thread_own(client, fake_ai):
    signup_and_login(client)
    client.post("/api/chat", json={"question": "기본 대화 질문"})
    tid = client.post("/api/threads").json()["id"]
    client.post("/api/chat", json={"question": "두 번째 대화 질문", "thread_id": tid})

    r = client.delete(f"/api/threads/{tid}")
    assert r.status_code == 200 and r.json() == {"deleted": True}
    assert client.get("/api/threads").json()[0]["id"] != tid


def test_delete_thread_cascades_logs(client, fake_ai):
    signup_and_login(client)
    client.post("/api/chat", json={"question": "남아야 할 질문"})
    tid = client.post("/api/threads").json()["id"]
    client.post("/api/chat", json={"question": "지워질 질문", "thread_id": tid})

    client.delete(f"/api/threads/{tid}")

    # 지운 스레드 조회는 404, 남은 로그만 본다
    assert client.get(f"/api/me/chats?thread_id={tid}").status_code == 404
    logs = client.get("/api/me/chats").json()
    assert [log["question"] for log in logs] == ["남아야 할 질문"]


def test_delete_thread_not_own_or_missing(client):
    signup_and_login(client, email="one@test.com")
    foreign = client.post("/api/threads").json()["id"]

    signup_and_login(client, email="two@test.com")
    assert client.delete(f"/api/threads/{foreign}").status_code == 404
    assert client.delete("/api/threads/999999").status_code == 404


def test_thread_cap_enforced(client, monkeypatch):
    signup_and_login(client)
    monkeypatch.setattr(settings, "max_threads_per_user", 2)
    assert client.post("/api/threads").status_code == 201
    assert client.post("/api/threads").status_code == 201
    r = client.post("/api/threads")
    assert r.status_code == 409
    assert "가득 찼어요" in r.json()["detail"]


def test_chat_with_foreign_or_missing_thread_404(client):
    signup_and_login(client, email="one@test.com")
    foreign = client.post("/api/threads").json()["id"]

    signup_and_login(client, email="two@test.com")
    assert (
        client.post("/api/chat", json={"question": "hi", "thread_id": foreign}).status_code == 404
    )
    assert client.post("/api/chat", json={"question": "hi", "thread_id": 999999}).status_code == 404
    # 404는 AI 호출 전(비용 방어) — 페이크 AI도 호출되지 않는다
    assert client.get("/api/me/chats").json() == []


def test_context_scoped_per_thread(client, fake_ai):
    """다른 대화의 Q/A는 AI 문맥에 섞이지 않는다 — 새 채팅 = 새 주제."""
    signup_and_login(client)
    # 기본 대화에 2개 질문
    client.post("/api/chat", json={"question": "기본 대화의 질문 하나"})
    client.post("/api/chat", json={"question": "기본 대화의 질문 둘"})

    # 새 대화 만들고 거기서 질문
    tid = client.post("/api/threads").json()["id"]
    client.post("/api/chat", json={"question": "새 대화의 질문 삼", "thread_id": tid})

    sent = " ".join(m["content"] for m in fake_ai.last_messages)
    assert "새 대화의 질문 삼" in sent
    assert "기본 대화의 질문 하나" not in sent
    assert "기본 대화의 질문 둘" not in sent


def test_context_within_thread_still_last_5(client, fake_ai):
    """스레드 안에서는 기존처럼 직전 5개 성공 Q/A만 — 6번째 질문은 문맥에서 빠진다."""
    signup_and_login(client)
    tid = client.post("/api/threads").json()["id"]
    for i in range(1, 7):
        client.post("/api/chat", json={"question": f"스레드 질문 {i}번", "thread_id": tid})

    client.post("/api/chat", json={"question": "지금까지 뭐라고 했지?", "thread_id": tid})
    sent = [m["content"] for m in fake_ai.last_messages]
    # 최근 5개(2~6번)는 있고, 가장 오래된 1번은 없다
    for i in range(2, 7):
        assert f"스레드 질문 {i}번" in sent
    assert "스레드 질문 1번" not in sent


def test_my_chats_thread_filter(client, fake_ai):
    signup_and_login(client)
    client.post("/api/chat", json={"question": "기본 대화 질문"})
    tid = client.post("/api/threads").json()["id"]
    client.post("/api/chat", json={"question": "스레드 질문", "thread_id": tid})

    only_thread = client.get(f"/api/me/chats?thread_id={tid}").json()
    assert [log["question"] for log in only_thread] == ["스레드 질문"]

    all_logs = client.get("/api/me/chats").json()
    assert len(all_logs) == 2

    # 남의 스레드 필터는 404
    signup_and_login(client, email="two@test.com")
    assert client.get(f"/api/me/chats?thread_id={tid}").status_code == 404


def test_title_autogenerated_from_first_question(client, fake_ai):
    signup_and_login(client)
    tid = client.post("/api/threads").json()["id"]
    question = "이것은 아주 긴 질문이야 ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    client.post("/api/chat", json={"question": question, "thread_id": tid})

    threads = client.get("/api/threads").json()
    new = next(t for t in threads if t["id"] == tid)
    expected = " ".join(question.split())[:20]
    assert new["title"] == expected
    assert len(new["title"]) <= 20


def test_default_thread_title_not_overwritten(client, fake_ai):
    """기본 대화('기본 대화' 제목)는 첫 질문으로 제목이 바뀌지 않는다."""
    signup_and_login(client)
    client.post("/api/chat", json={"question": "기본 대화 질문"})
    threads = client.get("/api/threads").json()
    assert threads[0]["title"] == "기본 대화"
