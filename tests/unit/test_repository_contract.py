"""CRUD 오류 경로와 관리자 테이블의 비파괴 추가."""

from contextlib import closing
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

from app.database import Base
from app.models import User
from app.repositories import chat_logs, users


def test_duplicate_race_becomes_a_domain_error(monkeypatch):
    db = Mock()
    monkeypatch.setattr(users, "find_by_email", Mock(side_effect=[None, User(id=1)]))
    db.commit.side_effect = IntegrityError("synthetic", {}, Exception("duplicate"))
    with pytest.raises(users.DuplicateEmailError):
        users.create_user(db, email="race@example.com", password_hash="hash", nickname="race")
    db.rollback.assert_called_once()


def test_log_failure_rolls_back(db, monkeypatch):
    monkeypatch.setattr(db, "commit", Mock(side_effect=RuntimeError("synthetic failure")))
    rollback = Mock(wraps=db.rollback)
    monkeypatch.setattr(db, "rollback", rollback)
    with pytest.raises(RuntimeError):
        chat_logs.save_log(
            db,
            user_id=1,
            question="synthetic",
            answer="",
            latency_ms=0,
            status="ai_error",
            request_id="test",
        )
    rollback.assert_called_once()


def test_admin_table_can_be_added_without_changing_existing_users(tmp_path):
    import sqlite3

    path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(path)) as db:
        db.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) UNIQUE, "
            "password_hash VARCHAR(255), nickname VARCHAR(50), created_at DATETIME)"
        )
        db.execute(
            "INSERT INTO users VALUES (1, 'existing@example.com', 'hash', '기존', "
            "'2026-09-08 00:00:00')"
        )
        db.commit()
    engine = create_engine("sqlite:///" + str(path))
    try:
        before = [c["name"] for c in inspect(engine).get_columns("users")]
        Base.metadata.create_all(engine)
        assert [c["name"] for c in inspect(engine).get_columns("users")] == before
        assert "admin_grants" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM users").scalar_one() == 1
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM admin_grants").scalar_one() == 0
    finally:
        engine.dispose()
