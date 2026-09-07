"""통합 테스트 — 회원가입/로그인/접근 제어."""
from tests.conftest import signup_and_login


def test_session_loss_blocks_protected_api(client):
    """세션 쿠키 소실/만료 시 보호 API 접근 차단 — 접근 제어 회귀 방지."""
    signup_and_login(client)
    assert client.get("/api/auth/me").status_code == 200

    client.cookies.clear()  # 세션 끊김(만료·브라우저 초기화) 시뮬레이션

    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/chat", json={"question": "안녕"}).status_code == 401
    assert client.get("/api/me/chats").status_code == 401


def test_signup_login_me_logout_flow(client):
    # 회원가입
    r = client.post("/api/auth/signup",
                    json={"email": "a@test.com", "password": "password123", "nickname": "홍"})
    assert r.status_code == 201
    assert r.json()["nickname"] == "홍"

    # 로그인 → 세션 쿠키 발급
    r = client.post("/api/auth/login", json={"email": "a@test.com", "password": "password123"})
    assert r.status_code == 200

    # 내 정보
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "a@test.com"

    # 로그아웃 → 다시 401
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_duplicate_signup_returns_409(client):
    body = {"email": "dup@test.com", "password": "password123"}
    assert client.post("/api/auth/signup", json=body).status_code == 201
    assert client.post("/api/auth/signup", json=body).status_code == 409


def test_wrong_password_returns_401(client):
    client.post("/api/auth/signup", json={"email": "b@test.com", "password": "password123"})
    r = client.post("/api/auth/login", json={"email": "b@test.com", "password": "wrong-pass"})
    assert r.status_code == 401


def test_signup_validation_short_password_422(client):
    r = client.post("/api/auth/signup", json={"email": "c@test.com", "password": "1234"})
    assert r.status_code == 422


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401


def test_stale_session_after_reseed_returns_401(client, db):
    """DB 재생성 후 stale 쿠키가 다른 계정으로 해석되지 않음 (#33)."""
    from app.models import User
    from app.services.security import hash_password

    signup_and_login(client, email="test@test.com")
    assert client.get("/api/auth/me").json()["email"] == "test@test.com"

    # DB 재생성: 전부 삭제 후 admin이 test의 옛 id(1)를 차지
    db.query(User).delete()
    db.add(User(email="admin@demo.com", password_hash=hash_password("x"), nickname="운영자"))
    db.commit()

    # stale 쿠키 → 401 + 세션 파기 (admin으로 오인 금지)
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/", follow_redirects=False).status_code == 302
