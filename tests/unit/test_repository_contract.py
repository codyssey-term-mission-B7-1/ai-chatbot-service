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


def test_admin_repository_functions(db):
    """admin repository의 조회 함수들이 정상 동작하는지 검증."""
    from datetime import datetime, timezone

    from app.repositories import admin as admin_repo

    # 통계 집계 검증
    horizon = datetime.now(timezone.utc)
    counts = admin_repo.get_admin_dashboard_counts(db, horizon)
    assert "users" in counts and "chats" in counts and "threads" in counts

    # 테이블 목록 조회 검증
    tables = admin_repo.get_table_counts(db)
    table_names = [name for name, _ in tables]
    assert "users" in table_names and "chat_logs" in table_names

    # 테이블 행 조회 검증
    res = admin_repo.get_table_rows(db, "users")
    assert res is not None
    rows, cols = res
    assert "email" in cols

    # 미지 테이블 조회 시 None 반환 검증
    assert admin_repo.get_table_rows(db, "unknown_table") is None
