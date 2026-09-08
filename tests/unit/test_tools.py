"""샘플 DB·로컬 Fake만 사용한 운영 도구 회귀 검사."""

import importlib.util
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backup_defaults_to_db_directory_and_preserves_source(tmp_path):
    tool = load_script("backup_db")
    path = tmp_path / "volume" / "app.db"
    path.parent.mkdir()
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE example (value TEXT)")
        db.execute("INSERT INTO example VALUES ('original')")
        db.commit()
    first = tool.backup(path)
    second = tool.backup(path)
    assert first != second and first.parent == path.parent / "backups"
    with closing(sqlite3.connect(second)) as db:
        assert db.execute("SELECT value FROM example").fetchall() == [("original",)]
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT value FROM example").fetchall() == [("original",)]
    if os.name != "nt":
        assert second.stat().st_mode & 0o777 == 0o600


def test_backup_retention_is_per_source_database(tmp_path):
    tool = load_script("backup_db")
    destination = tmp_path / "backups"
    sources = [tmp_path / "one.db", tmp_path / "two.db"]
    for source in sources:
        with closing(sqlite3.connect(source)) as db:
            db.execute("CREATE TABLE example (id INTEGER)")
    other = tool.backup(sources[1], destination, keep=2)
    for _ in range(3):
        tool.backup(sources[0], destination, keep=2)
    assert other.exists() and len(list(destination.glob("*.db"))) == 3


def test_backup_explicit_path_does_not_create_a_missing_source(tmp_path):
    tool = load_script("backup_db")
    import pytest

    with pytest.raises(ValueError):
        tool.database_path(str(tmp_path / "missing.db"))
    assert not (tmp_path / "missing.db").exists()


def test_ai_check_fake_result_is_not_a_real_connection_claim():
    env = dict(os.environ, AI_API_KEY="", DEBUG="true", DATABASE_URL="sqlite://")
    run = subprocess.run(
        [sys.executable, "scripts/ai_check.py"], cwd=ROOT, env=env, capture_output=True, text=True
    )
    assert run.returncode == 0 and "데모 동작 정상" in run.stdout
    assert "실 AI 연결 성공 증거가 아닙니다" in run.stdout
    run = subprocess.run(
        [sys.executable, "scripts/ai_check.py", "--require-real"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 2 and "수행하지 않았습니다" in run.stderr


def test_admin_cli_help_does_not_need_application_secrets():
    env = dict(os.environ)
    env.pop("SESSION_SECRET", None)
    env["DEBUG"] = "false"
    run = subprocess.run(
        [sys.executable, "scripts/manage_admin.py", "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0 and "grant" in run.stdout


def test_experiment_is_twelve_requests_and_restores_global_settings():
    from app.config import settings

    tool = load_script("experiment_context_turns")
    before = settings.context_turns
    row = tool.measure(3)
    assert tool.TOTAL_TURNS == 12
    assert row["oldest_turn"] == "9" and row["messages"] == 8 and row["past_pairs"] == 3
    assert settings.context_turns == before


def test_fresh_seed_preserves_non_demo_users_and_logs(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.models import ChatLog, User

    tool = load_script("seed_mock_data")
    engine = create_engine("sqlite:///" + str(tmp_path / "seed-test.db"))
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with factory() as db:
        user = User(email="real-user@example.com", password_hash="test-only", nickname="보존")
        db.add(user)
        db.commit()
        db.add(
            ChatLog(user_id=user.id, question="보존할 질문", answer="보존할 답", status="success")
        )
        db.commit()
    monkeypatch.setattr(tool, "engine", engine)
    monkeypatch.setattr(tool, "SessionLocal", factory)
    try:
        tool.seed(fresh=False)
        tool.seed(fresh=True)
        with factory() as db:
            assert db.query(User).filter(User.email == "real-user@example.com").count() == 1
            assert db.query(ChatLog).filter(ChatLog.question == "보존할 질문").count() == 1
    finally:
        engine.dispose()
