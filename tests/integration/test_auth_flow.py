"""통합 테스트 — 회원가입/로그인/접근 제어."""


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
