"""DB 엔진/세션 — SQLite 기본, PostgreSQL/MySQL 전환 가능.

스키마 관리는 Alembic이 담당한다(alembic/versions/). 앱 시작 시 create_all은
테스트/빈 DB에만 사용하고, 기존 DB는 `alembic upgrade head`로 누락 마이그레이션만
적용한다. SQLite 특정 PRAGMA는 SQLite일 때만 붙인다.

연결 풀 정책:
- SQLite 파일 DB: 기본 SingletonThreadPool(단일 연결 재사).
- SQLite 인메모리(``sqlite://`` / ``sqlite:///:memory:``): StaticPool + check_same_thread=False.
  없으면 연결마다 새 인메모리 DB가 생겨 create_all로 만든 테이블이 요청 처리 시점에
  보이지 않는다 (테스트 환경의 흔한 함정).
- Postgres/MySQL: QueuePool + pool_pre_ping + pool_recycle.
"""

from pathlib import Path

from sqlalchemy import create_engine, event, inspect
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
_is_sqlite_memory = _is_sqlite and settings.database_url in ("sqlite://", "sqlite:///:memory:")

_engine_kwargs: dict = {}
if _is_sqlite_memory:
    # 인메모리 DB는 모든 연결이 같은 DB를 가리켜야 한다(테스트 lifespan에서 create_all 한
    # 테이블이 요청 처리 연결에서도 보여야).
    from sqlalchemy.pool import StaticPool

    _engine_kwargs.update(
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
elif _is_sqlite:
    _engine_kwargs.update(connect_args={"check_same_thread": False})
else:
    # TCP 연결 타임아웃을 짧게(3초) 잡아 DB 장애 시 /readyz가 수십 초씩 블로킹되지 않게 한다.
    # 드라이버별 키가 달라 넓은 안전망으로만 적용한다.
    _engine_kwargs.update(
        connect_args={"connect_timeout": 3},
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        pool_pre_ping=True,
        pool_timeout=3,
    )
engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _sqlite_pragmas_on_connect(dbapi_conn, _conn_record):
    """SQLite는 연결마다 설정이 초기화된다. 매 연결에서 다시 켠다.

    - foreign_keys=ON: FK 검증과 ON DELETE CASCADE가 실제로 작동하게 (#51).
    - journal_mode=WAL: 읽기-쓰기 동시성 개선. 파일 DB에만 적용.
    - busy_timeout: 잠금 경합 시 최대 5초 대기.
    """
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    if settings.database_url not in ("sqlite://", "sqlite:///:memory:"):
        cur.execute("PRAGMA journal_mode=WAL")
    cur.close()


if _is_sqlite:
    event.listens_for(engine, "connect")(_sqlite_pragmas_on_connect)


def _has_any_table() -> bool:
    """DB에 어떤 테이블이라도 있는지 — 빈 DB 판단용."""
    with engine.connect() as conn:
        return bool(inspect(conn).get_table_names())


def init_db() -> None:
    """앱 시작 시 스키마를 동기화.

    - 인메모리/테스트/완전히 빈 파일 DB: Base.metadata.create_all로 테이블을 만들고
      alembic stamp head로 최신 리비전을 마킹.
    - 기존 DB: ``alembic upgrade head``로 누락 마이그레이션만 적용.
    """
    import os

    from alembic import command
    from alembic.config import Config

    in_memory = settings.database_url in ("sqlite://", "sqlite:///:memory:")
    is_test = os.environ.get("TESTING") == "1"
    ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    if in_memory or is_test or not _has_any_table():
        Base.metadata.create_all(bind=engine)
        command.stamp(alembic_cfg, "head")
        return
    command.upgrade(alembic_cfg, "head")


def get_db():
    """요청마다 DB 세션을 생성/반환하는 FastAPI 의존성."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
