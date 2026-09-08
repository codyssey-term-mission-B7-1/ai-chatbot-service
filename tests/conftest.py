"""테스트 공용 fixture — 인메모리 DB + Fake AI (실 API 호출 금지)."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")  # 테스트 중 파일 DB 생성 방지
os.environ.setdefault("DEBUG", "1")  # 테스트는 개발 컨텍스트 — http 쿠키/임시 시크릿 허용

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.ai_client import get_ai_provider  # noqa: E402

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def _test_fk_connection(connection, _record):
    connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture(autouse=True)
def _isolated_login_limiter():
    """로그인 실패 제한기를 테스트마다 초기화하고 여유 한도로 완화한다.

    잠금 전용 테스트는 낮은 한도를 직접 지정해 확인한다. 기본 5회 그대로면
    우연히 겹치는 이메일을 쓰는 다른 테스트가 서로 오염시킬 수 있다.
    """
    from app.services.rate_limit import login_limiter

    saved = (login_limiter.max_events, login_limiter.window_seconds)
    login_limiter.max_events = 10_000
    login_limiter.reset()
    yield
    login_limiter.max_events, login_limiter.window_seconds = saved
    login_limiter.reset()


TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


class FakeAIProvider:
    """AI API를 흉내내는 페이크 — reply/error로 시나리오 제어."""

    def __init__(self):
        self.reply = "테스트 응답입니다."
        self.error = None
        self.last_messages: list[dict] = []

    async def generate(self, messages: list[dict]) -> str:
        self.last_messages = messages
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture()
def fake_ai(db):
    provider = FakeAIProvider()

    def _override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_ai_provider] = lambda: provider
    app.dependency_overrides[get_db] = _override_get_db
    yield provider
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db, fake_ai):
    with TestClient(app) as c:
        yield c


def signup_and_login(client: TestClient, email="tester@example.com", password="Test1234!"):
    """통합 테스트용 헬퍼 — 가입 + 로그인(세션 쿠키 발급)."""
    client.post("/api/auth/signup", json={"email": email, "password": password})
    client.post("/api/auth/login", json={"email": email, "password": password})
