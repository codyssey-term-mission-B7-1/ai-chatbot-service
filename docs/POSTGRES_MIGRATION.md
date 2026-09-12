# SQLite → PostgreSQL 전환 가이드

본 서비스는 현재 SQLite를 기본 DB로 쓰고 있지만, 스키마/쿼리/타입이 **PostgreSQL 호환**으로 정리되어 있고 스키마 마이그레이션은 **Alembic**이 관리한다. 따라서 연결 문자열만 바꾸고 드라이버를 설치한 뒤 마이그레이션을 실행하면 Postgres로 전환할 수 있다.

> 본 가이드는 코드가 준비되어 있음을 보이는 문서다. 실제 운영 전환은 팀이 데이터 이전 계획과 다운타임을 별도로 검토한 뒤 진행한다.

## 1. 드라이버 설치

SQLite 기본 의존성에 psycopg2를 추가로 설치한다(기본 requirements에는 포함하지 않아 SQLite 사용 환경에서 불필요한 바이너리 설치를 피한다):

```bash
pip install psycopg2-binary
# (필요하다면 requirements에 고정)
echo "psycopg2-binary>=2.9" >> requirements.txt
```

MySQL의 경우: `pip install pymysql`, URL 스킴은 `mysql+pymysql://…`.

## 2. PostgreSQL 프로비저닝 (Railway 예)

1. Railway 대시보드 → 프로젝트 → **New → Add Postgres**.
2. Postgres 서비스의 `DATABASE_PUBLIC_URL`(또는 `DATABASE_URL`) 변수를 복사한다.
   - 포맷: `postgresql://postgres:xxxx@postgres.railway.internal:5432/railway` (내부)
   - 퍼블릭: `postgresql://postgres:xxxx@xxxx.railway.app:5432/railway`
3. GitHub Secrets / Railway 변수의 `DATABASE_URL`을 이 값으로 교체한다.
   - sqlite:////data/app.db → postgresql://…
4. `RAILWAY_VOLUME_MOUNT_PATH` 등 볼륨 의존 변수는 더 이상 사용하지 않으므로 제거 가능.

## 3. 스키마 생성 (최초 전환)

Postgres DB가 비어 있는 상태라면:

```bash
# 로컬에서 연결(로컬 개발머신에서 원격 Postgres 접속 가능 시):
export DATABASE_URL='postgresql://...'
alembic upgrade head
```

Railway 배포 시에는 **앱 시작이 자동으로 `alembic upgrade head`를 실행**(`app/database.py:init_db`)하므로 첫 배포에서 테이블이 자동 생성된다. (기존 SQLite DB 데이터는 자동 이전되지 않는다. 아래 §5 참조.)

## 4. SQLite 특정 도구 영향

| 파일/도구 | Postgres에서의 동작 | 대응 |
|---|---|---|
| `scripts/check_logs.sql` | sqlite3 CLI 전용 `.mode column`/`.print` 메타 명령이 안 먹음 | 데이터 조회는 `/admin/logs` UI나 `psql`로 직접 쿼리. 이 스크립트는 SQLite에서만 쓴다고 상단 주석에 명시. |
| `scripts/backup_db.py` | sqlite3 전용 백업 API(`source.backup`)를 사용 | Postgres 전환 시 `pg_dump`/`pg_restore`로 교체. Railway는 자동 스냅샷이 제공된다. |
| `scripts/backup_db.sh` | SQLite 호출 스크립트 | 백업 정책 재설정 필요. |
| PRAGMA (`foreign_keys`, `WAL`, `busy_timeout`) | SQLite 전용 — `app/database.py`가 dialect 분기로 자동 스킵 | 별도 조치 불필요. |
| 테스트 conftest | 여전히 인메모리 SQLite(`sqlite://`) 사용 | 테스트는 빠르고 결정적이게 유지 (SQLite <> PG 차이가 있는 부분은 별도 통합 테스트를 추가). |

## 5. 기존 SQLite 데이터 이전

앱 시작 마이그레이션은 스키마만 만들고 데이터를 이전하지 않는다. 실제 데이터 이전은 별도 작업이 필요하다. 간단한 방법:

1. SQLite를 CSV로 내보내고 Postgres로 COPY:
   ```bash
   sqlite3 /data/app.db ".mode csv" ".headers on" ".once users.csv" "SELECT id,email,password_hash,nickname,created_at FROM users;"
   # chat_logs / admin_grants / session_revocations / password_resets 도 동일하게
   psql "$DATABASE_URL" -c "\copy users(id,email,password_hash,nickname,created_at) FROM 'users.csv' WITH (FORMAT csv, HEADER);"
   ```
   주의: `password_resets`는 만료된 토큰이 많을 수 있으니 전환 직후 `DELETE FROM password_resets;` 로 비우는 것이 안전하다.
2. 더 안전한 도구: `pgloader` (SQLite → Postgres 스키마/데이터 자동 마이그레이션).
3. 전환 직후 모든 기존 세션 쿠키는 새 시크릿을 쓰거나 스키마 구조 변경 시 무효화될 수 있으니 전체 로그아웃(`scripts/revoke_sessions.py` 전체 사용자 순회)을 고려한다.

## 6. 앱에서 자동 적용되는 Postgres 전용 설정

`app/database.py`가 DSN 스킴(`postgresql` 포함)을 보고 다음을 자동 적용한다:

- `pool_size=5`, `max_overflow=10` (커넥션 풀)
- `pool_recycle=1800` (30분 이상 묵은 커넥션 재생성, Railway 등 프록시 연결 끊김 방지)
- `pool_pre_ping=True` (체크아웃 전 쿼리로 죽은 커넥션 감지)

SQLite 커넥션에는 이 옵션이 전달되지 않으므로(에러가 나므로) 개발/기존 운영에는 영향 없다.

## 7. 확인 목록

- [ ] 로컬에서 `DATABASE_URL=postgresql://... alembic upgrade head` 성공
- [ ] 앱 기동 로그에 에러 없음 (세션 시크릿/페퍼는 기존과 동일하게 유지)
- [ ] `/health` → `{"status":"ok","ai_mode":"real"}`
- [ ] 가입 → 로그인 → 채팅 → 내 기록 조회 → 관리자 조회 전부 정상
- [ ] CI 통과 (CI는 여전히 SQLite 인메모리로 빠르게 돎)
- [ ] 백업 정책: sqlite backup 스크립트가 아닌 pg_dump/Railway 스냅샷으로 전환
- [ ] 다중 워커(uvicorn `--workers N`)를 쓸 경우 rate limit이 메모리 기반임을 인지. 필요 시 Redis 기반 limiter로 교체(AUDIT_HARDENING.md B-5).

## 8. 롤백

전환 후 문제가 생기면 DATABASE_URL을 다시 `sqlite:////data/app.db`로 돌리고 재배포하면 SQLite로 롤백된다. (Postgres에 쌓인 새 데이터는 자동으로 SQLite로 돌아오지 않으므로 다운타임 계획 시 양방향 동기화는 별도 구현이 필요하다.)

---

*문서 버전: 2026-09-12 · Alembic 도입과 함께 작성*
