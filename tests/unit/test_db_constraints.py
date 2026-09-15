"""DB 층 방어 단위 테스트 — CHECK 제약이 백엔드 우회 입력을 거부하는지(#183)."""

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app.database import Base
from app.models import ChatLog, Thread, User
from app.policies import QUESTION_ABS_MAX_CHARS


@pytest.fixture()
def bare_db():
    """앱 파이프라인 없이 순수 DB만 — 제약 자체를 검증한다."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(email="seed@test.com", password_hash="x" * 60, nickname="seed")
    session.add(user)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _seed_user_id(session) -> int:
    return session.query(User).first().id


def test_reject_invalid_chat_status(bare_db):
    session = bare_db
    with pytest.raises(IntegrityError):
        session.execute(
            insert(ChatLog).values(
                user_id=_seed_user_id(session),
                question="질문",
                answer="답",
                status="hacked_status",
            )
        )
    session.rollback()


def test_reject_blank_or_oversized_question(bare_db):
    session = bare_db
    uid = _seed_user_id(session)
    with pytest.raises(IntegrityError):
        session.execute(
            insert(ChatLog).values(user_id=uid, question="   ", answer="답", status="success")
        )
    session.rollback()
    with pytest.raises(IntegrityError):
        session.execute(
            insert(ChatLog).values(
                user_id=uid,
                question="가" * (QUESTION_ABS_MAX_CHARS + 1),
                answer="",
                status="ai_error",
            )
        )
    session.rollback()


def test_reject_oversized_user_fields(bare_db):
    session = bare_db
    with pytest.raises(IntegrityError):
        session.add(User(email="a" * 256 + "@t.com", password_hash="x" * 60, nickname="n"))
        session.commit()
    session.rollback()
    with pytest.raises(IntegrityError):
        session.add(User(email="ok@test.com", password_hash="x" * 60, nickname="n" * 51))
        session.commit()
    session.rollback()


def test_reject_oversized_thread_title(bare_db):
    session = bare_db
    with pytest.raises(IntegrityError):
        session.add(Thread(user_id=_seed_user_id(session), title="제" * 61))
        session.commit()
    session.rollback()
