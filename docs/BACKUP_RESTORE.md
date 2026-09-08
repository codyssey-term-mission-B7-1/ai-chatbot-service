# SQLite 백업·복원 정책

## 목표와 현재 범위

RPO 24시간 / RTO 1시간은 **운영 목표**다. 일일 스케줄러 등록과 실제 복원 드릴이 완료되어야 달성 여부를 판단할 수 있다. 현재 자동으로 운영 스케줄러를 만들지는 않는다.

## 온라인 백업

```bash
# 명시적 경로: 이 경우 Python 표준 라이브러리만 사용
./scripts/backup_db.sh /data/app.db

# 목적지/보관 세대/시간 예산 명시
./scripts/backup_db.sh /data/app.db --backup-dir /data/backups --keep 7 --timeout 30

# 프로젝트 의존성 설치 환경: DATABASE_URL 또는 .env에서 경로 읽기
python scripts/backup_db.py
```

- 명시적 DB 경로가 없으면 프로세스 `DATABASE_URL` → `.env`의 `DATABASE_URL` → 로컬 기본 app.db 순으로 선택한다.
- 기본 백업 위치는 **실제 DB 파일과 같은 디렉터리의 `backups/`**다. `/data/app.db`이면 `/data/backups/`가 된다. CWD에 따라 다른 디스크에 쓰지 않는다.
- `--backup-dir` 또는 `BACKUP_DIR`로 바꾼 경로가 실제 영구 볼륨인지 운영자가 확인해야 한다.
- DB가 없으면 실패하며 빈 원본 DB를 만들지 않는다. 원본은 읽기 전용으로 열고 SQLite 온라인 backup API를 사용한다.
- 무결성 검증에 실패한 새 백업은 삭제한다. 성공한 백업에는 SHA-256을 출력한다.
- 파일명은 DB 경로 식별자 + UTC 마이크로초 + 무작위 식별자를 포함한다. 같은 초의 두 실행도 덮어쓰지 않는다.
- 최근 7세대는 **같은 원본 DB 그룹별**로 보관한다. 다른 DB의 백업을 섞어 삭제하지 않는다.
- 새 백업 파일은 Unix에서 0600으로 생성한다. `.env`와 시크릿은 백업에 넣지 않는다.

## 운영 적용

1. DB와 백업 디렉터리를 영구 볼륨에 둔다.
2. 배포 플랫폼 스케줄러로 매일 백업을 실행한다. 실제 등록 결과를 증빙으로 남긴다.
3. 별도 보관소에 주기적으로 내려받아 저장한다. **서버 밖 보관 위치·책임자·보존 기간은 운영자가 확정해야 한다.**
4. DB 변경/대량 시딩 전에는 추가 백업과 복구 가능성을 확인한다.

## 복원 — 서버 정지 후 운영자가 수행

아래 경로는 예시다. 대상 파일을 확인하지 않고 실행하지 않는다.

```bash
# 1. 서버/워커를 정지한다. WAL/SHM 파일과 활성 연결도 점검한다.
# 2. 현재 DB를 별도 경로에 보관한다. 덮어쓰지 말고 먼저 백업한다.
python scripts/backup_db.py /data/app.db --backup-dir /data/pre-restore
# 3. 선택한 백업본의 무결성과 해시를 확인한다.
python -c "import sqlite3; c=sqlite3.connect('/data/backups/선택한백업.db'); print(c.execute('PRAGMA integrity_check').fetchall()); c.close()"
# 4. 서버가 정지한 상태에서 검증된 백업을 복원한다.
# cp /data/backups/선택한백업.db /data/app.db
# 5. 재기동 후 /health, 로그인, 본인/관리자 권한, 대화 조회를 검증한다.
```

백업 복원은 스키마 마이그레이션이 아니다. `create_all`은 기존 열이나 FK를 바꾸지 않는다. 예전 FK 스키마의 데이터를 보존해야 한다면 별도의 마이그레이션·행 수 대조·foreign_key_check 절차를 먼저 설계해야 한다.

로컬 테스트는 합성 DB의 온라인 백업·무결성·세대 분리·소스 보존을 검증한다. 운영 RPO/RTO나 실제 복원 성공을 대신 증명하지 않는다.
