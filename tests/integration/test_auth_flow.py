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
    r = client.post(
        "/api/auth/signup",
        json={"email": "a@test.com", "password": "password123", "nickname": "홍"},
    )
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


def test_email_case_insensitive_signup_login(client):
    """대소문자 달라도 동일 계정 — 정규화 후 중복 409 + 교차 로그인 (#4)."""
    r = client.post("/api/auth/signup", json={"email": "Case@Test.com", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["email"] == "case@test.com"

    r = client.post("/api/auth/signup", json={"email": "case@test.com", "password": "password123"})
    assert r.status_code == 409  # 정규화 후 중복

    r = client.post("/api/auth/login", json={"email": "CASE@TEST.COM", "password": "password123"})
    assert r.status_code == 200


def test_session_cookie_carries_no_plaintext_email(client):
    """쿠키는 base64 인코딩일 뿐 암호화가 아니다 — 페이로드에 email이 남으면 안 된다 (#59)."""
    import base64
    import json

    from tests.conftest import signup_and_login

    signup_and_login(client, email="noleak@example.com")
    signed = client.cookies.get("session")
    payload = json.loads(base64.b64decode(signed.split(".")[0] + "=="))
    assert "email" not in payload, payload
    assert "email_fp" in payload, payload
    assert "noleak@example.com" not in base64.b64decode(signed.split(".")[0] + "==").decode()


def test_session_cookie_expiry_is_one_day_by_default(client):
    """Starlette 기본 14일이 아니라 SESSION_MAX_AGE_HOURS(기본 24시간)를 따른다 (#12·#55·#74)."""
    from tests.conftest import signup_and_login

    signup_and_login(client, email="exp@example.com")
    # 재로그인 없이 직접 확인: 세션 저장 시 쿠키 헤더를 살펴본다
    r = client.post("/api/auth/login", json={"email": "exp@example.com", "password": "Test1234!"})
    cookie = r.headers.get_list("set-cookie")[0]
    assert "Max-Age=86400" in cookie, cookie


def test_signup_whitespace_only_password_422(client):
    """공백만으로 구성된 비밀번호는 8자 이상이어도 거부된다(스페이스/개행/탭)."""
    for blank in ["        ", "\n\n\n\n\n\n\n\n", "\t \t \t \t "]:
        r = client.post("/api/auth/signup", json={"email": "blank-pw@test.com", "password": blank})
        assert r.status_code == 422
        assert "공백만으로" in r.text


def test_legacy_hash_login_rehashes_to_peppered(client, db):
    """페퍼 도입 전 레거시 해시 — 로그인 성공 시 페퍼 적용 해시로 자동 재저장된다."""
    import bcrypt as _bcrypt

    from app.models import User

    email = "legacy@test.com"
    legacy_hash = _bcrypt.hashpw("LegacyPass123!".encode(), _bcrypt.gensalt()).decode()
    db.add(User(email=email, password_hash=legacy_hash, nickname="레거시"))
    db.commit()

    r = client.post("/api/auth/login", json={"email": email, "password": "LegacyPass123!"})
    assert r.status_code == 200

    db.expire_all()
    refreshed = db.query(User).filter_by(email=email).one()
    assert refreshed.password_hash != legacy_hash
    from app.services.security import verify_password

    assert verify_password("LegacyPass123!", refreshed.password_hash) is True


def test_login_blank_email_or_password_shows_422_or_401(client):
    """빈/공백 이메일·비밀번호 로그인 시도 — 서버는 422(형식) 또는 401(불일치)로 응답."""
    r = client.post("/api/auth/login", json={"email": "   ", "password": "   "})
    assert r.status_code in (401, 422)
