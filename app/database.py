"""DB 엔진/세션 — SQLite 기본, PostgreSQL/MySQL 전환 가능."""

from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
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
    from sqlalchemy.pool import StaticPool

    _engine_kwargs.update(
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
elif _is_sqlite:
    _engine_kwargs.update(connect_args={"check_same_thread": False})
else:
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
    """SQLite는 연결마다 설정이 초기화된다. 매 연결에서 다시 켠다."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    if settings.database_url not in ("sqlite://", "sqlite:///:memory:"):
        cur.execute("PRAGMA journal_mode=WAL")
    cur.close()


if _is_sqlite:
    event.listens_for(engine, "connect")(_sqlite_pragmas_on_connect)

schema_sync = {"status": "pending", "error": None, "revision": None}


def _classify_db_error(exc: Exception) -> str:
    """예외 상세를 노출하지 않으면서도 원인 식별이 되는 짧은 코드."""
    msg = str(exc).lower()
    if "legacy schema incomplete" in msg:
        return "legacy_incomplete"
    if "already exists" in msg:
        return "table_exists"
    if "no such table" in msg:
        return "no_such_table"
    if "no such column" in msg:
        return "no_such_column"
    if "database is locked" in msg:
        return "db_locked"
    if "readonly database" in msg:
        return "db_readonly"
    if "disk i/o error" in msg:
        return "db_io_error"
    if "database or disk is full" in msg:
        return "db_full"
    return type(exc).__name__


def _has_any_table(eng) -> bool:
    """DB에 어떤 테이블이라도 있는지 — 빈 DB 판단용."""
    with eng.connect() as conn:
        return bool(inspect(conn).get_table_names())


def _has_alembic_version_table(eng) -> bool:
    with eng.connect() as conn:
        return "alembic_version" in inspect(conn).get_table_names()


def _has_version_row(eng) -> bool:
    """``alembic_version``에 실제 리비전 행이 있는지 — 빈 테이블(0행)은 레거시 상태다."""
    with eng.connect() as conn:
        try:
            return conn.execute(text("SELECT 1 FROM alembic_version LIMIT 1")).first() is not None
        except Exception:
            return False


def _schema_is_current(eng) -> bool:
    """현재 DB가 모델이 요구하는 모든 테이블·컬럼을 포함하는지."""
    with eng.connect() as conn:
        insp = inspect(conn)
        have_tables = set(insp.get_table_names())
        for name, table in Base.metadata.tables.items():
            if name not in have_tables:
                return False
            have_cols = {c["name"] for c in insp.get_columns(name)}
            if not {c.name for c in table.columns} <= have_cols:
                return False
    return True


def _adopt_legacy_schema(alembic_cfg, eng) -> None:
    """``alembic_version``이 없는 레거시 DB에 리비전 마크를 부여한다."""
    from alembic import command
    from alembic.script import ScriptDirectory

    if _schema_is_current(eng):
        command.stamp(alembic_cfg, "head")
        return
    roots = [
        rev
        for rev in ScriptDirectory.from_config(alembic_cfg).walk_revisions()
        if rev.down_revision is None
    ]
    if len(roots) != 1:
        raise RuntimeError(
            f"레거시 DB 인수(adopt)은 단일 루트 리비전을 전제로 한다 (검출: {len(roots)}개)."
        )
    command.stamp(alembic_cfg, roots[0].revision)


def init_db(alembic_cfg=None, eng=None) -> None:
    """앱 시작 시 스키마를 동기화."""
    import os

    import app.models  # noqa: F401 — Base.metadata에 모든 모델이 등록되도록
    from alembic import command
    from alembic.config import Config

    target = engine if eng is None else eng
    if alembic_cfg is None:
        ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
        alembic_cfg = Config(str(ini_path))

    try:
        in_memory = str(target.url) in ("sqlite://", "sqlite:///", "sqlite:///:memory:")
        is_test = os.environ.get("TESTING") == "1"
        if in_memory or is_test or not _has_any_table(target):
            Base.metadata.create_all(bind=target)
            command.stamp(alembic_cfg, "head")
        else:
            if not _has_alembic_version_table(target) or not _has_version_row(target):
                _adopt_legacy_schema(alembic_cfg, target)
            command.upgrade(alembic_cfg, "head")
            if not _schema_is_current(target):
                raise RuntimeError(
                    "Legacy schema incomplete: 스키마가 최신이 아님 — "
                    "root 이전 구조의 DB는 데이터 백업 후 초기화하세요."
                )
    except Exception as exc:
        schema_sync.update(status="error", error=_classify_db_error(exc), revision=None)
        raise

    try:
        with target.connect() as conn:
            revision = conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar()
    except Exception:
        revision = None
    schema_sync.update(status="ok", error=None, revision=revision)


def get_db():
    """요청마다 DB 세션을 생성/반환하는 FastAPI 의존성."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
