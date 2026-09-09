"""이메일 기반 비밀번호 재설정 — 존재 은닉·토큰 수명·요청 상한·세션 폐기 통합 검증."""

import re
import time

import pytest
from sqlalchemy import select, update

from app.models import PasswordReset
from tests.conftest import signup_and_login

EMAIL = "reset-user@example.com"
OLD_PASSWORD = "OldPass123!"
NEW_PASSWORD = "NewPass456!"


def request_reset(client, email=EMAIL):
    return client.post("/api/auth/password/reset-request", json={"email": email})


def extract_token(sent):
    """페이크 SMTP가 기록한 메일 본문에서 재설정 링크의 토큰을 추출한다."""
    (message,) = sent["messages"]
    match = re.search(r"http\S+/reset-password\?token=(\S+)", message.get_content())
    assert match, "메일 본문에 재설정 링크가 없습니다"
    return match.group(1)


@pytest.fixture()
def fake_smtp(monkeypatch):
    """SMTP 대역 페이크 — 설정을 채우고 발송된 메시지를 기록한다."""
    from app.config import settings
    from app.services import password_reset as svc

    sent = {"messages": []}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def send_message(self, message):
            sent["messages"].append(message)

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test", raising=False)
    monkeypatch.setattr(settings, "smtp_user", "mailer@example.test", raising=False)
    monkeypatch.setattr(svc.smtplib, "SMTP", FakeSMTP)
    return sent


def test_unknown_email_gets_same_202_without_side_effects(client, db, fake_smtp):
    """미가입 이메일도 동일 202 — 존재 여부 누출 금지, 토큰·메일도 없다."""
    response = request_reset(client, email="nobody@example.com")
    assert response.status_code == 202
    assert db.scalars(select(PasswordReset)).all() == []
    assert fake_smtp["messages"] == []


def test_request_stores_hash_and_sends_link(client, db, fake_smtp):
    signup_and_login(client, email=EMAIL, password=OLD_PASSWORD)
    db.query(PasswordReset).delete()
    db.commit()

    response = request_reset(client)
    assert response.status_code == 202

    rows = db.scalars(select(PasswordReset)).all()
    assert len(rows) == 1
    token = extract_token(fake_smtp)
    # DB에는 원문 토큰이 아니라 해시만 저장된다
    assert rows[0].token_hash != token
    assert len(rows[0].token_hash) == 64
    assert rows[0].used_epoch is None


def test_complete_changes_password_and_revokes_sessions(client, db, fake_smtp):
    signup_and_login(client, email=EMAIL, password=OLD_PASSWORD)
    db.query(PasswordReset).delete()
    db.commit()
    # 폐기 기준은 초 단위(+1초 백오프) — 같은 초에 발급된 세션과 구분하기 위해
    # 재설정 전 세션을 1초 이상 과거로 만든다(#78의 sleep(1.1) 패턴과 동일).
    time.sleep(1.1)
    request_reset(client)
    token = extract_token(fake_smtp)

    response = client.post(
        "/api/auth/password/reset", json={"token": token, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 200

    # 기존 세션은 즉시 폐기 — 재설정 즉시 재로그인 유도
    assert client.get("/api/auth/me").status_code == 401
    # 이전 비밀번호로는 로그인 불가, 새 비밀번호로 로그인 성공
    assert client.post(
        "/api/auth/login", json={"email": EMAIL, "password": OLD_PASSWORD}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}
    ).status_code == 200


def test_token_is_single_use(client, db, fake_smtp):
    signup_and_login(client, email=EMAIL, password=OLD_PASSWORD)
    db.query(PasswordReset).delete()
    db.commit()
    request_reset(client)
    token = extract_token(fake_smtp)

    first = client.post(
        "/api/auth/password/reset", json={"token": token, "new_password": NEW_PASSWORD}
    )
    assert first.status_code == 200
    second = client.post(
        "/api/auth/password/reset", json={"token": token, "new_password": "Again789!"}
    )
    assert second.status_code == 400


def test_expired_token_is_rejected(client, db, fake_smtp):
    signup_and_login(client, email=EMAIL, password=OLD_PASSWORD)
    db.query(PasswordReset).delete()
    db.commit()
    request_reset(client)
    token = extract_token(fake_smtp)

    db.execute(
        update(PasswordReset).values(expires_epoch=int(time.time()) - 60)
    )
    db.commit()

    response = client.post(
        "/api/auth/password/reset", json={"token": token, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 400


def test_invalid_token_is_rejected(client):
    signup_and_login(client, email=EMAIL, password=OLD_PASSWORD)
    response = client.post(
        "/api/auth/password/reset",
        json={"token": "x" * 43, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400


def test_request_rate_limit_suppresses_fourth_email(client, db, fake_smtp):
    """상한(기본 3회/15분) 초과 요청은 같은 202를 반환하지만 메일을 보내지 않는다."""
    signup_and_login(client, email=EMAIL, password=OLD_PASSWORD)
    db.query(PasswordReset).delete()
    db.commit()

    for _ in range(3):
        assert request_reset(client).status_code == 202
    fourth = request_reset(client)
    assert fourth.status_code == 202  # 존재 누출 방지 — 응답은 동일
    assert len(fake_smtp["messages"]) == 3
    assert len(db.scalars(select(PasswordReset)).all()) == 3


def test_production_without_smtp_returns_503(client, db, monkeypatch):
    """운영(DEBUG=false)에서 SMTP 미설정은 503 — 설정 상태는 계정 정보가 아니므로 명시적 안내."""
    from app.config import settings

    monkeypatch.setattr(settings, "smtp_host", "", raising=False)
    monkeypatch.setattr(settings, "debug", False, raising=False)
    signup_and_login(client, email=EMAIL, password=OLD_PASSWORD)
    db.query(PasswordReset).delete()
    db.commit()

    response = request_reset(client)
    assert response.status_code == 503


def test_dev_mode_without_smtp_logs_link(client, db, caplog):
    """개발 모드는 202와 함께 재설정 링크를 서버 로그로만 출력한다."""
    signup_and_login(client, email=EMAIL, password=OLD_PASSWORD)
    db.query(PasswordReset).delete()
    db.commit()

    with caplog.at_level("WARNING", logger="app.password_reset"):
        response = request_reset(client)
    assert response.status_code == 202
    assert any("reset-password?token=" in r.message for r in caplog.records)


def test_reset_pages_render_according_to_token_validity(client, db, fake_smtp):
    signup_and_login(client, email=EMAIL, password=OLD_PASSWORD)
    db.query(PasswordReset).delete()
    db.commit()
    request_reset(client)
    token = extract_token(fake_smtp)
    client.post("/api/auth/logout")

    forgot = client.get("/forgot-password")
    assert forgot.status_code == 200
    assert "forgot-form" in forgot.text

    valid_page = client.get(f"/reset-password?token={token}")
    assert valid_page.status_code == 200
    assert 'id="reset-form"' in valid_page.text
    assert token in valid_page.text

    invalid_page = client.get("/reset-password?token=invalid-token-value-1234567890ab")
    assert invalid_page.status_code == 200
    assert "유효하지 않거나 만료" in invalid_page.text
    assert 'id="reset-form"' not in invalid_page.text

    login_page = client.get("/login")
    assert "/forgot-password" in login_page.text
