#!/usr/bin/env python3
"""SQLite 온라인 백업. 기본 목적지는 실제 DB와 같은 디렉터리의 backups/.

명시적 DB 경로를 주면 표준 라이브러리만 사용한다. 경로 생략 시 DATABASE_URL 또는
.env의 SQLite URL을 읽는다(이 경우 프로젝트 의존성 필요). 운영 DB 삭제/복원은 하지 않는다.
"""
import argparse
import datetime
import hashlib
import os
import re
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from contextlib import closing


def database_path(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
    else:
        from dotenv import dotenv_values
        from sqlalchemy.engine import make_url
        values = dotenv_values('.env') if Path('.env').exists() else {}
        url = make_url(os.environ.get('DATABASE_URL') or values.get('DATABASE_URL')
                       or 'sqlite:///./app.db')
        if url.get_backend_name() != 'sqlite' or not url.database or url.database == ':memory:':
            raise ValueError('기존 SQLite 파일 경로를 명시하거나 올바른 DATABASE_URL을 설정하세요.')
        if url.query.get('uri') == 'true':
            raise ValueError('URI 모드 대신 실제 SQLite 파일 경로를 인수로 주세요.')
        path = Path(url.database).expanduser().resolve()
    if not path.is_file():
        raise ValueError('백업할 DB 파일이 없습니다. 경로를 확인하세요.')
    return path


def backup(database: Path, destination: Path | None = None, keep: int = 7,
           timeout: float = 30.0) -> Path:
    if keep < 1 or timeout <= 0:
        raise ValueError('keep은 1 이상, timeout은 양수여야 합니다.')
    database = database.resolve(strict=True)
    directory = (destination or database.parent / 'backups').resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    group = hashlib.sha256(str(database).encode()).hexdigest()[:8]
    stem = re.sub(r'[^A-Za-z0-9_-]', '_', database.stem) or 'db'
    prefix = f'{stem}_{group}_'
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    target = directory / f'{prefix}{stamp}_{uuid.uuid4().hex[:8]}.db'
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    deadline = time.monotonic() + timeout

    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError('백업 시간 예산을 초과했습니다.')

    try:
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=5)) as source:
            with closing(sqlite3.connect(target)) as dest:
                source.backup(dest, pages=256, progress=progress, sleep=0.05)
                checks = dest.execute('PRAGMA integrity_check').fetchall()
                if checks != [('ok',)]:
                    raise ValueError('백업본 무결성 검사 실패')
    except Exception:
        target.unlink(missing_ok=True)
        raise
    generations = sorted((x for x in directory.glob(prefix + '*.db')
                          if x.is_file() and not x.is_symlink()),
                         key=lambda x: x.stat().st_mtime_ns, reverse=True)
    for old in generations[keep:]:
        old.unlink()
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', nargs='?')
    parser.add_argument('--backup-dir', type=Path)
    parser.add_argument('--keep', type=int, default=7)
    parser.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args(argv)
    try:
        source = database_path(args.database)
        destination = args.backup_dir
        if destination is None and os.environ.get('BACKUP_DIR'):
            destination = Path(os.environ['BACKUP_DIR'])
        target = backup(source, destination, args.keep, args.timeout)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        print(f'백업 완료: {target}')
        print(f'integrity=ok sha256={digest} keep={args.keep}')
        return 0
    except (ValueError, OSError, sqlite3.Error, TimeoutError) as exc:
        print(f'백업 실패: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
