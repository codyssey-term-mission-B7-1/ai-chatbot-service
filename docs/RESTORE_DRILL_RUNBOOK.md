# 복원 드릴 런북 (Restore Drill) — RPO/RTO 실측 절차

> 목적: TODO.md의 "복원 드릴/RPO/RTO 실측" 미완료 항목 해소. **복원을 해보기 전까지 백업은 존재하지 않는 것과 같다.**
> 소요: 최초 1회 약 30분(운영 볼륨 크기에 따라 가감). 분기 1회 반복 권장.

## 사전 준비

- 운영 DB 백업 1세대 확보: `scripts/backup_db.sh` (Railway Shell 또는 로컬 동기화본)
- 스테이징 위치: 로컬 작업 디렉터리 또는 별도 Railway 프로젝트(운영 인스턴스에 절대 덮어쓰지 않는다)

## 드릴 절차 (측정값을 각 칸에 기록)

| 단계 | 명령/행위 | 측정 |
|---|---|---|
| 1. 백업 확보 | `bash scripts/backup_db.sh /data/app.db --backup-dir /data/backups --keep 7` | 시작 시각 T0 기록 |
| 2. 무결성 검증 | `sqlite3 backups/xxx.db "PRAGMA integrity_check;"` → `ok` | 출력 캡처 |
| 3. 해시 대조 | 백업 스크립트가 출력한 SHA-256과 재계산 대조 | 일치 여부 |
| 4. 복원 대상 준비 | 빈 디렉터리에 백업 파일 복사(`cp`) | |
| 5. 앱 기동 | `DATABASE_URL=sqlite:///복원경로/app.db uvicorn app.main:app --port 8900` | 기동 완료 시각 T1 |
| 6. 읽기 성공 | `curl :8900/health` 200 + 데모 계정 로그인 + `/api/me/chats` 본인 기록 반환 | 응답 캡처 |
| 7. 쓰기 성공 | 채팅 1회(데모 모드) → `chat_logs` 행 증가 확인 | |
| 8. 손실 구간 산출 | 마지막 정상 백업 이후 운영에서 발생한 대화 수 = 데이터 손실분 | RPO = 백업 주기 |
| 9. 정리 | 드릴용 프로세스/파일 폐기, 결과 기록 | RTO = T1 − T0 |

## 기록 템플릿 (docs/evidence/restore-drill-YYYY-MM-DD.md로 저장)

```
- 실시: 2026-09-XX (담당: ooo)
- 백업 세대: backups/app-YYYYMMDD-HHMMSS.db (SHA-256: ...)
- 무결성: ok / 해시 대조: 일치
- RTO 실측: XX분 XX초 (목표: 30분 이내)
- RPO: 수동 백업 = 마지막 실행 이후 전체 (백업 스케줄러 도입 전까지 "비상시 최대 하루 손실 가능" 고지)
- 발견 결함: (예: .env 재설정 필요, pepper 불일치로 로그인 불가 → 운영 pepper 백업 필요)
```

## 알려진 함정 (드릴에서 반드시 걸리는 것들)

1. **PASSWORD_PEPPER는 백업에 없다** — 복원 환경에 운영과 동일한 페퍼를 Secret으로 넣어야 로그인 검증이 통과한다. 페퍼 백업은 비밀 보관소(서버 밖)에 별도 보관.
2. WAL 파일(-wal/-shm)이 남아 있으면 복사본이 불완전할 수 있다 → 백업 스크립트의 온라인 백업 경로(sqlite3 backup API)를 그대로 쓰고, 파일 복사는 금지.
3. 복원 후 `/health`가 `ai_mode=demo`여도 정상이다 — 드릴 목적은 데이터이지 AI가 아니다.

## 목표 수치 (초안 — 실측 후 확정)

- RTO 목표: 30분 이내 (재배포 + 복원 + 검증)
- RPO 목표: 백업 스케줄러 도입 전 "1일", 도입 후 "1시간"
