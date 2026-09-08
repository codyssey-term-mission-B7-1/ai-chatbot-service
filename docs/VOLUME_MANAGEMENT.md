# 볼륨·디스크 관리

## 현재 구현과 운영 목표

| 대상 | 구현/위치 | 운영 주의 |
|---|---|---|
| SQLite DB | DATABASE_URL. 로컬 기본 app.db / Railway 기본 /data/app.db | /data가 실제 영구 Volume인지 검증해야 함 |
| 표준 이벤트 | 기본 stderr | stdout만 리디렉션하지 말고 실제 플랫폼 수집 설정 확인 |
| 백업 | 기본 실제 DB 디렉터리의 backups/ | 명시적 --backup-dir/BACKUP_DIR도 영구 저장소인지 확인 |
| 관리자 권한 | admin_grants, 기본 빈 테이블 | 공개 데모 계정에 권한을 주지 않음 |
| 업로드 | 미지원 | 임의 파일 저장 API 없음 |

`ensure_sqlite_dir`은 부모 디렉터리를 만드는 함수이지, 그 경로가 영구 볼륨인지 증명하지 않는다.

## 용량·보존

- DB 경고 100MB / 위험 500MB는 운영 기준 제안이다. 실제 측정과 경보 연결이 필요하다.
- 백업은 원본 DB 그룹별 최근 7개를 보관한다. 같은 초 실행도 고유 파일명이며 다른 DB의 백업을 섞어 삭제하지 않는다.
- 보존 기간/RPO/RTO는 운영자가 확정한다. 현재 코드가 운영 스케줄러나 아카이브를 자동 배포하지 않는다.
- 질문·답변 크기와 사용자 수에 따라 증가량이 달라진다. “1만 건=20MB”를 고정 보장으로 사용하지 않는다.
- 채팅 로그는 자동 삭제하지 않는다. `seed_mock_data.py --fresh`는 지정된 데모 계정과 그 계정의 기록만 초기화한다. 일반 사용자 기록은 삭제하지 않지만, 운영 데이터베이스에서 데모 데이터를 생성하는 것은 피한다.

## 점검 예

```bash
# 실제 DATABASE_URL 경로를 확인한 후 사용
DU_DB=/data/app.db
du -h "$DU_DB" /data/backups/
# 백업 생성 및 무결성 확인
python scripts/backup_db.py "$DU_DB"
```

stdout/stderr 수집, 로그 보존과 접근 통제는 플랫폼에서 확인한다. 파일 로그로 바꿀 경우 영구 볼륨·로테이션·권한·개인정보 처리를 함께 결정한다.

[백업·복원](BACKUP_RESTORE.md) · [이벤트 계약](LOGGING.md) · [배포 런북](RAILWAY_DEPLOY.md)
