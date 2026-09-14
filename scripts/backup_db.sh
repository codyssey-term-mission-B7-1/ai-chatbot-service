#!/usr/bin/env bash
# SQLite 온라인 백업. DB 경로 생략 시 DATABASE_URL/.env 사용.
# 기본 백업 위치: 실제 DB 파일과 같은 디렉터리의 backups/.
# 명시적 목적지: ./scripts/backup_db.sh /data/app.db --backup-dir /data/backups --keep 7
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/backup_db.py" "$@"
