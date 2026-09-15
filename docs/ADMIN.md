# 앱 관리자 운영

## 기본 정책

- **기본 권한 없음.** 회원가입 요청에 관리자 플래그를 넣을 수 없다.
- GitHub 관리자/역할 카드 담당자/닉네임은 앱 관리자 자격이 아니다.
- `admin_grants` 테이블에서 사용자 ID와 당시 이메일을 묶어 권한을 부여한다. ID가 다른 이메일 계정으로 재사용되면 권한이 이어지지 않는다.
- 이 테이블은 `create_all`로 비파괴 생성된다. 기존 `users` 열을 추가·변경하지 않는다. 기존 다른 스키마/FK의 마이그레이션을 대신하지는 않는다.
- 관리자 API도 로그인과 세션-계정 바인딩 검증을 거친다. 비로그인 401, 일반 사용자 403.

## 권한 부여/회수

**신뢰된 서버 운영자만** 해당 서비스의 DB를 가리키는 환경에서 실행한다. 이 명령을 HTTP 엔드포인트로 노출하지 않는다.

1. 공개 데모 계정이 아닌 전용 계정을 정상 회원가입으로 생성하고 실제 계정 통제를 확인한다. 이메일 소유 확인 기능은 없으므로, 이메일 문자열만 보고 이미 존재하는 타인 계정을 승격하지 않는다. 중복 409가 나오면 먼저 실제 계정을 확인한다.
2. 운영자는 대상 DB와 계정을 확인한 후 부여한다.

```bash
# 서비스 루트, 올바른 DATABASE_URL 및 운영 SESSION_SECRET 환경에서 실행
python scripts/manage_admin.py grant --email operator@example.com
python scripts/manage_admin.py list
python scripts/manage_admin.py revoke --email operator@example.com
```

`operator@example.com`은 예시다. 실제 대상 계정을 확인해야 한다. 공개 비밀번호가 있는 `demo@demo.com`, `tester@demo.com`, `admin@demo.com`은 승격을 거부한다. 권한 회수는 다음 요청부터 반영되며 쿠키 만료를 기다리지 않는다.

## 조회

### 관리자 콘솔 (/admin)

사이드바의 **관리자 콘솔**에서 진입하며 하위 메뉴 5종으로 구성된다(#189):

| 메뉴 | 경로 | 내용 |
|---|---|---|
| 대시보드 | `/admin` | 사용자·스레드·대화·성공률·최근 24h 요청/이벤트 카드 |
| 채팅 로그 | `/admin/logs` | 전체 대화 원문 조회 — 필터 쿼리, 열람 사유 |
| 이벤트 로그 | `/admin/events` | 감사 이벤트 DB 영속분(audit_events, 보존 5,000건) — 필터 쿼리 |
| 네트워크 로그 | `/admin/network` | /api/ 요청 기록(request_logs, 보존 5,000건) — 필터 쿼리 |
| 데이터베이스 | `/admin/db` | 테이블 목록·행수·최근 행 미리보기(읽기 전용, 화이트리스트) |

### 필터 쿼리 문법(#201)

`키:값` 토큰을 공백으로 나열하면 AND. 접두사 없는 단어는 전체 검색어. 입력 중 힌트가 지원 키·적용 요약·미지 키를 표시한다.

| 화면 | 키 | 예 |
|---|---|---|
| 채팅 로그 | `email:` `thread:` `status:` `q:` | `email:user@example.com thread:3 q:배포` |
| 이벤트 로그 | `event:` `user:` `q:` | `event:ai_call_fail user:2` |
| 네트워크 로그 | `path:` `method:` `status:` `user:` | `path:/api/chats method:POST status:500` |
| 데이터베이스 | `table:` | `table:users` |

- 같은 키는 API에서도 `?filter=` 로 사용 가능(CLI `logs_client` 호환).
- 미지 키는 화면 하단 오류 힌트로 표시되고 무시된다. 값은 모두 바인딩 파라미터로만 사용된다(임의 SQL 없음).

- 웹 셸 터미널은 의도적으로 제공하지 않는다 — 관리자 세션 탈취 시 서버 전체 장악(RCE)으로 이어지는 안티패턴.
- 이벤트·네트워크 로그 기록은 best-effort다. 기록 실패가 사용자 요청 처리에 영향을 주지 않는다(테스트 `test_recorder_failure_never_breaks_requests`).
- 열람 행위 자체도 감사 이벤트(admin_*_viewed)로 기록된다.


- 화면: `/admin/logs` — 사용자 ID 필터, 최근 50건, 이전 페이지
- API: `GET /api/admin/chats?limit=50&user_id=12&status=success&before_id=100`
- 생략 가능한 필터: `user_id`, `status`, `before_id`. `limit`은 1~200으로 제한한다.
- 응답: `{ "items": [...], "next_before_id": 51 }`. 마지막 페이지가 정확히 limit개이면 다음 페이지가 비어 있을 수도 있다.
- 일반 `/api/users/me/chats`는 관리자로 로그인해도 본인 기록만 반환한다.

대화 원문에는 개인정보가 있을 수 있다. 화면 접근 자체를 `admin_logs_viewed`로 기록하지만 이 이벤트에는 질문·응답 원문을 넣지 않는다. 증빙을 공유할 때는 실제 개인정보·쿠키·키를 제거한다.

## 검증 범위

`tests/integration/test_admin.py`와 로컬 브라우저 증빙은 합성 계정/DB 기반이다. 운영 관리자 계정을 만들어 부여했다는 증거가 아니다.
