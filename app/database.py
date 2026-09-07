"""SQLAlchemy 엔진/세션 — SQLite."""
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def ensure_sqlite_dir(database_url: str) -> None:
    """sqlite 파일 경로의 부모 디렉터리 보장 (Railway Volume 등 마운트 경로 방어)."""
    if not database_url.startswith("sqlite:///"):
        return
    db_path = database_url.removeprefix("sqlite:///")
    if db_path in ("", ":memory:"):
        return
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


ensure_sqlite_dir(settings.database_url)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _fk_pragma_on_connect(dbapi_conn, _conn_record):
    """SQLite는 연결마다 foreign_keys가 기본 off다.

    매 연결에서 켜야 FK 검증과 ON DELETE CASCADE가 실제로 작동한다 (#51).
    """
    if settings.database_url.startswith("sqlite"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


if settings.database_url.startswith("sqlite"):
    event.listens_for(engine, "connect")(_fk_pragma_on_connect)


def get_db():
    """요청마다 DB 세션을 생성/반환하는 FastAPI 의존성."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
