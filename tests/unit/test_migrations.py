"""마이그레이션(Alembic) 단위 테스트.

Alembic이 빈 DB에서 `upgrade head`로 전체 스키마를 만들고, 모델 metadata와
테이블 집합이 동일한지 검증한다. 앱 config를 거치지 않고 Alembic 자체 engine으로
마이그레이션을 실행해 환경변수/전역 engine 의존성을 피한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect

from alembic import command
from alembic.config import Config

ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    # 환경변수/앱 settings를 덮어쓰도록 sqlalchemy.url을 명시 설정.
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    return cfg


def _sqlite_pragmas(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


@pytest.fixture()
def fresh_sqlite_url(tmp_path):
    """매 테스트마다 빈 SQLite 파일 DB URL을 제공."""
    db_path = tmp_path / "fresh.db"
    db_path.touch()
    yield f"sqlite:///{db_path.resolve()}"


def test_upgrade_head_creates_all_tables(fresh_sqlite_url):
    cfg = _alembic_config(fresh_sqlite_url)
    command.upgrade(cfg, "head")

    engine = create_engine(fresh_sqlite_url)
    event.listens_for(engine, "connect")(_sqlite_pragmas)
    try:
        tables = sorted(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert "alembic_version" in tables
    for expected in (
        "users",
        "chat_logs",
        "threads",
        "admin_grants",
        "session_revocations",
        "password_resets",
    ):
        assert expected in tables, f"테이블 {expected}가 마이그레이션으로 생성되어야 한다."


def test_legacy_db_without_version_table_is_adopted(fresh_sqlite_url, monkeypatch):
    """레거시 DB(alembic 도입 전 create_all 생성, alembic_version 없음) — base 스탬프 후
    누락 마이그레이션이 적용된다. 2026-09-13 운영 사고 재발 방지: 버전 테이블 없이
    upgrade 하면 init 재실행 → 'table users already exists'로 항상 실패해
    lifespan이 삼키며 스키마가 갱신되지 않았다."""
    from sqlalchemy import text

    monkeypatch.delenv("TESTING", raising=False)
    cfg = _alembic_config(fresh_sqlite_url)
    command.upgrade(cfg, "9dea740a4bf1")  # init 스키마만

    engine = create_engine(fresh_sqlite_url)
    event.listens_for(engine, "connect")(_sqlite_pragmas)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, nickname, created_at) "
                "VALUES ('legacy@example.com', 'hash', '레거시', '2026-01-01 00:00:00+00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO chat_logs "
                "(user_id, question, answer, latency_ms, status, request_id, created_at) "
                "VALUES (1, '레거시 질문', '레거시 답변', 10, 'success', "
                "'req1', '2026-01-02 00:00:00+00:00')"
            )
        )
        conn.execute(text("DROP TABLE alembic_version"))  # ★ ceed2b7 이전 운영 DB 상태
    engine.dispose()

    from app.database import init_db

    engine = create_engine(fresh_sqlite_url)
    event.listens_for(engine, "connect")(_sqlite_pragmas)
    try:
        init_db(alembic_cfg=cfg, eng=engine)

        insp = inspect(engine)
        assert "threads" in insp.get_table_names()
        assert "thread_id" in [c["name"] for c in insp.get_columns("chat_logs")]
        with engine.connect() as conn:
            assert (
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                == "c7e4a9b21d05"
            )
            titles = conn.execute(text("SELECT title FROM threads")).fetchall()
            assert titles == [("기본 대화",)]
            nulls = conn.execute(
                text("SELECT COUNT(*) FROM chat_logs WHERE thread_id IS NULL")
            ).scalar()
            assert nulls == 0, "레거시 기록이 기본 대화에 귀속되어야 한다."
    finally:
        engine.dispose()


def test_legacy_db_with_current_schema_gets_head_stamp(fresh_sqlite_url, monkeypatch):
    """최신 스키마인데 버전 테이블만 없는 DB — head 스탬프만, 마이그레이션 재실행 없음."""
    from sqlalchemy import text

    monkeypatch.delenv("TESTING", raising=False)
    cfg = _alembic_config(fresh_sqlite_url)
    command.upgrade(cfg, "head")

    engine = create_engine(fresh_sqlite_url)
    event.listens_for(engine, "connect")(_sqlite_pragmas)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, nickname, created_at) "
                "VALUES ('cur@example.com', 'hash', '최신', '2026-01-01 00:00:00+00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO threads (user_id, title, created_at, updated_at) "
                "VALUES (1, '보존될 제목', '2026-01-02 00:00:00+00:00', "
                "'2026-01-02 00:00:00+00:00')"
            )
        )
        conn.execute(text("DROP TABLE alembic_version"))
    engine.dispose()

    from app.database import init_db

    engine = create_engine(fresh_sqlite_url)
    event.listens_for(engine, "connect")(_sqlite_pragmas)
    try:
        init_db(alembic_cfg=cfg, eng=engine)
        with engine.connect() as conn:
            head = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert head == "c7e4a9b21d05"
            # 스탬프만 — 기존 데이터에 손대지 않는다
            titles = conn.execute(text("SELECT title FROM threads")).fetchall()
            assert titles == [("보존될 제목",)]
    finally:
        engine.dispose()


def test_threads_migration_backfills_legacy_rows(fresh_sqlite_url):
    """기존 DB(레거시) 업그레이드: 사용자당 '기본 대화' 생성 + 기존 기록을 그 스레드에 귀속."""
    from sqlalchemy import text

    cfg = _alembic_config(fresh_sqlite_url)
    command.upgrade(cfg, "9dea740a4bf1")  # threads 없는 옛 스키마

    engine = create_engine(fresh_sqlite_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, nickname, created_at) "
                "VALUES ('legacy@example.com', 'hash', '레거시', '2026-01-01 00:00:00+00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO chat_logs "
                "(user_id, question, answer, latency_ms, status, request_id, created_at) "
                "VALUES (1, '레거시 질문', '레거시 답변', 10, 'success', "
                "'req1', '2026-01-02 00:00:00+00:00')"
            )
        )
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = create_engine(fresh_sqlite_url)
    event.listens_for(engine, "connect")(_sqlite_pragmas)
    try:
        with engine.connect() as conn:
            threads = conn.execute(text("SELECT id, user_id, title FROM threads")).fetchall()
            assert len(threads) == 1 and threads[0][2] == "기본 대화"
            thread_id = threads[0][0]
            rows = conn.execute(text("SELECT thread_id FROM chat_logs")).fetchall()
            assert all(
                row[0] == thread_id for row in rows
            ), "레거시 기록이 기본 대화에 귀속되어야 한다."
    finally:
        engine.dispose()


def test_models_metadata_matches_head(fresh_sqlite_url):
    """Base.metadata와 마이그레이션 결과의 테이블 집합이 일치한다."""
    # 모델을 임포트해 metadata를 채운다. 전역 DATABASE_URL에 의존하지 않는다.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.database import Base  # noqa: PLC0415

    cfg = _alembic_config(fresh_sqlite_url)
    command.upgrade(cfg, "head")

    engine = create_engine(fresh_sqlite_url)
    event.listens_for(engine, "connect")(_sqlite_pragmas)
    try:
        migrated = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    model_tables = {t.name for t in Base.metadata.sorted_tables}
    assert (model_tables - migrated) == set(), "모델에 정의된 테이블이 마이그레이션에 누락됨"
    extra_in_db = {
        n
        for n in (migrated - model_tables - {"alembic_version"})
        if not n.startswith("sqlite_autoindex_")
    }
    assert extra_in_db == set(), f"마이그레이션이 모델에 없는 테이블을 만듦: {extra_in_db}"
