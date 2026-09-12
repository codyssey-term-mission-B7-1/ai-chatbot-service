"""Alembic 환경 설정 — 앱 config/database/Base를 공유한다.

- SQLite는 ALTER TABLE 제약이 있어 배치 마이그레이션 모드로 렌더링한다.
- PostgreSQL/MySQL은 온라인 ALTER를 그대로 사용.
- url은 코드에서 주입(.ini에 하드코딩하지 않음) — 시크릿/환경별 DSN은
  코드 단일 소스(settings.database_url)에서 가져온다.
"""

from __future__ import annotations

import logging
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, text

from alembic import context

# 프로젝트 루트를 sys.path에 추가해 app 패키지를 임포트할 수 있게 한다.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.models import Base  # noqa: E402  # 모든 모델이 Base.metadata에 등록되게 한다.


def _pragma_for(url: str):
    """주어진 URL에 대해 연결 이벤트에 붙일 PRAGMA 핸들러를 반환한다."""

    def _handler(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        if url not in ("sqlite://", "sqlite:///:memory:"):
            cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return _handler


config = context.config

# fileConfig가 기존 로거를 끊지(disable_existing_loggers) 않게 한다. 앱 import 시
# 설정된 로거와 caplog가 TestClient 생명주기 안에서 무력화되는 현상을 막는다.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

logger = logging.getLogger("alembic.env")
target_metadata = Base.metadata


def _resolve_url() -> str:
    """Alembic config에 명시된 url이 있으면 우선 쓰고, 없으면 앱 settings에서 가져온다.

    테스트에서는 file 경로 url을 명시 주입한다.
    """
    from_cfg = config.get_main_option("sqlalchemy.url")
    if from_cfg:
        return from_cfg
    return settings.database_url


def _is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    """offline 모드: SQL만 출력. DB 연결 불필요."""
    url = _resolve_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _connectable():
    """Alembic이 사용할 엔진을 구성한다.

    - SQLite: 파일 DB는 기본 SingletonThreadPool, 인메모리는 StaticPool,
      매 연결 PRAGMA(foreign_keys/busy_timeout/journal_mode)를 적용한다.
    - Postgres/MySQL: NullPool(일회성 마이그레이션에 충분).
    """
    from sqlalchemy.pool import NullPool, StaticPool

    url = _resolve_url()
    app_config = config.get_section(config.config_ini_section, {})
    app_config["sqlalchemy.url"] = url
    kwargs: dict = {"prefix": "sqlalchemy."}
    if url.startswith("sqlite"):
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["poolclass"] = NullPool
    connectable = engine_from_config(app_config, **kwargs)
    if _is_sqlite_url(url):
        from sqlalchemy import event as sa_event

        sa_event.listens_for(connectable, "connect")(_pragma_for(url))
    return connectable


def run_migrations_online() -> None:
    """online 모드: 실제 DB에 마이그레이션 실행."""
    connectable = _connectable()
    url = _resolve_url()
    is_sqlite = _is_sqlite_url(url)
    with connectable.connect() as connection:
        # SQLite 배치 모드: 제약 있는 ALTER를 테이블 재생성으로 우회.
        # 타입/기본값 비교를 켜서 컬럼 타입 변경도 마이그레이션에 반영.
        # 초기 마이그레이션(init)에서는 테이블 생성 시 인덱스를 일괄 생성(batch mode
        # 없이)한다. 기존 테이블 스키마 변경이 있을 때는 render_as_batch=True가 필요하나,
        # 현재 리비전(init)에서는 테이블 생성뿐이므로 False로 둬도 SQLite에서 안전하다.
        # 향후 열 추가/변경 리비전이 생기면 해당 리비전 안에서 op.batch_alter_table를
        # 직접 사용하거나 여기서 render_as_batch을 동적으로 켤 수 있다.
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=False,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            # SQLite는 트랜잭션 DDL을 그대로 지원. Postgres도 일반 DDL은 트랜잭션 내에서
            # 안전하다(일부 DDL(CREATE INDEX CONCURRENTLY 등)은 예외이나 지금 없음).
            if is_sqlite:
                # SQLite는 기본적으로 FK 제약이 꺼져 있어 마이그레이션 중에 일관성이 깨질 수
                # 있다. 배치 모드와 함께 PRAGMA foreign_keys를 여기서도 강제한다.
                connection.execute(text("PRAGMA foreign_keys=ON"))
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
