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

_is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}
_engine_kwargs: dict = {"connect_args": connect_args}
if not _is_sqlite:
    # SQLite는 SingletonThreadPool(pool_size=1 고정)을 쓰므로 풀 관련 인자를 주면 에러.
    # Postgres/MySQL 전환 시 stale 커넥션 정리와 과도한 동시 접속을 방지한다.
    _engine_kwargs.update(
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _sqlite_pragmas_on_connect(dbapi_conn, _conn_record):
    """SQLite는 연결마다 설정이 초기화된다. 매 연결에서 다시 켠다.

    - foreign_keys=ON: FK 검증과 ON DELETE CASCADE가 실제로 작동하게 (#51).
    - journal_mode=WAL: 읽기-쓰기 동시성 개선(A-3 — 쓰기 잠금 경합을 늦춘다).
      파일 DB에만 유효(:memory:는 무시됨). WAL은 DB 파일 옆에 -wal/-shm을 만들며,
      백업 스크립트의 온라인 백업 경로와 무관하게 일관성 있는 스냅샷을 보장한다.
    - busy_timeout: 쓰기 잠금 경합 시 즉시 'database is locked'로 실패하지 않고
      최대 5초까지 대기(A-2의 db_save_fail 원인 중 잠금 경합 축소).
    """
    if settings.database_url.startswith("sqlite"):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        if settings.database_url not in ("sqlite://", "sqlite:///:memory:"):
            cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


if settings.database_url.startswith("sqlite"):
    event.listens_for(engine, "connect")(_sqlite_pragmas_on_connect)


def get_db():
    """요청마다 DB 세션을 생성/반환하는 FastAPI 의존성."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
