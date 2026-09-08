"""유닛 테스트 — sqlite 부모 디렉터리 보장 (볼륨 경로 방어)."""

from app.database import ensure_sqlite_dir


def test_ensure_sqlite_dir_creates_missing_parent(tmp_path):
    target = tmp_path / "volume" / "app.db"
    ensure_sqlite_dir(f"sqlite:///{target}")
    assert target.parent.is_dir()


def test_ensure_sqlite_dir_skips_memory_and_relative():
    ensure_sqlite_dir("sqlite://")  # 인메모리 — 예외 없이 통과
    ensure_sqlite_dir("sqlite:///:memory:")
    ensure_sqlite_dir("sqlite:///./app.db")  # 현재 디렉터리 — 이미 존재


def test_sqlite_foreign_keys_pragma_is_on():
    """PRAGMA foreign_keys는 연결 단위 기본 off — 매 연결에서 켜야 FK가 강제된다 (#51)."""
    from sqlalchemy import text

    from app.database import engine

    with engine.connect() as conn:
        assert bool(conn.execute(text("PRAGMA foreign_keys")).scalar())


def test_chat_logs_fk_ddl_has_on_delete_cascade():
    """README §4의 '사용자 삭제 시 로그도 삭제' 약속이 SQL 레벨에도 존재해야 한다 (#51)."""
    from sqlalchemy.schema import CreateTable

    from app.models import ChatLog

    assert "ON DELETE CASCADE" in str(CreateTable(ChatLog.__table__)).upper()


def test_raw_sql_user_delete_removes_logs(tmp_path):
    """원시 SQL 삭제 경로(평가자·Railway 셸)에서도 고아 로그가 남으면 안 된다 (#51)."""
    from sqlalchemy import create_engine, event, text
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.models import ChatLog, User  # noqa: F401

    eng = create_engine(
        f"sqlite:///{tmp_path / 'fk.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _on(dbapi_conn, _rec):
        dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users(id,email,password_hash,nickname,created_at)"
                " VALUES (901,'c@d.e','h','c','2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO chat_logs(user_id,question,answer,latency_ms,status,request_id,"
                "created_at) VALUES (901,'q','a',1,'success','r','2026-01-01')"
            )
        )
        conn.execute(text("DELETE FROM users WHERE id=901"))
        left = conn.execute(text("SELECT COUNT(*) FROM chat_logs WHERE user_id=901")).scalar()
    assert left == 0
    eng.dispose()


def test_fk_rejects_orphan_log(tmp_path):
    """FK 강제 활성화 후엔 없는 사용자의 로그 삽입은 실패해야 한다 (#51)."""
    import pytest
    from sqlalchemy import create_engine, event, text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.models import ChatLog, User  # noqa: F401

    eng = create_engine(
        f"sqlite:///{tmp_path / 'fk2.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _on(dbapi_conn, _rec):
        dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    with pytest.raises(IntegrityError), eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO chat_logs(user_id,question,answer,latency_ms,status,request_id,"
                "created_at) VALUES (4242,'q','a',1,'success','r','2026-01-01')"
            )
        )
    eng.dispose()
