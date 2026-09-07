#!/usr/bin/env bash
# DB 온라인 백업 스크립트 — 실행 중에도 무결성 보장
# 사용법: ./scripts/backup_db.sh [DB경로=app.db]
# 정책: docs/BACKUP_RESTORE.md (7세대 보관, 무결성 검증 포함)
# 의존: sqlite3 CLI 없으면 python3 표준라이브러리(sqlite3 모듈)로 동작 (Windows 등)
set -euo pipefail
DB="${1:-app.db}"
BACKUP_DIR="backups"
KEEP=7

[ -f "$DB" ] || { echo "❌ DB 파일 없음: $DB"; exit 1; }
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/app_${STAMP}.db"

# ── 백업 (온라인 API 사용 — cp 금지) ──
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB" ".backup '$DEST'"
  CHECK=$(sqlite3 "$DEST" "PRAGMA integrity_check;" 2>&1)
else
  python3 - "$DB" "$DEST" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
    s.backup(d)          # 온라인 백업 API (실행 중 안전)
    result = d.execute("PRAGMA integrity_check;").fetchone()[0]
    print(result)
PY
  CHECK=$(python3 - "$DEST" <<'PY'
import sqlite3, sys
print(sqlite3.connect(sys.argv[1]).execute("PRAGMA integrity_check;").fetchone()[0])
PY
)
fi

if [ "$CHECK" != "ok" ]; then
  echo "❌ 백업본 무결성 검증 실패, 삭제: $DEST ($CHECK)"
  rm -f "$DEST"
  exit 1
fi
echo "✅ 백업 완료: $DEST ($(du -h "$DEST" | cut -f1)) — integrity: $CHECK"

# ── 세대 관리: 최근 KEEP개만 유지 ──
ls -1t "$BACKUP_DIR"/app_*.db 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f "$old"
  echo "🗑️  세대 초과 삭제: $old"
done
echo "보관 현황: $(ls -1 "$BACKUP_DIR"/app_*.db | wc -l)/$KEEP 세대"
