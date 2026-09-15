"""관리자 전용 기능 — 전체 대화 조회·해시 현황·사용자 삭제. 권한은 서버 CLI로만 부여한다."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_admin_user
from app.models import User
from app.policies import DEFAULT_PAGE_SIZE, MAX_AUDIT_REASON_CHARS
from app.schemas import (
    AdminDbRows,
    AdminDbTableOut,
    AdminEventPage,
    AdminLogPage,
    AdminRequestLogPage,
    DeletedUserOut,
    LogStatus,
    PasswordHashStatusOut,
)
from app.services.admin import (
    delete_user_by_admin,
    get_admin_chats_page,
    get_admin_dashboard_stats,
    get_admin_db_table_rows,
    get_admin_db_tables,
    get_admin_events_page,
    get_admin_requests_page,
    get_password_hash_migration_status,
)
from app.services.suggest import MAX_SUGGESTIONS, SUGGESTORS

logger = logging.getLogger("app.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get(
    "/chats",
    response_model=AdminLogPage,
    summary="관리자 대화 로그 조회",
    description=(
        "명시적 앱 관리자만 전체 사용자 기록 조회 가능. 원문은 관리자 화면에만 "
        "표시하고 접근 이벤트에는 원문을 기록하지 않습니다."
    ),
    responses={401: {"description": "로그인 필요"}, 403: {"description": "앱 관리자 권한 필요"}},
)
def all_chats(
    filter_query: str = Query(default="", max_length=200, alias="filter"),
    limit: int = DEFAULT_PAGE_SIZE,
    user_id: int | None = Query(default=None, gt=0),
    thread_id: int | None = Query(default=None, gt=0),
    status_: LogStatus | None = Query(default=None, alias="status"),
    before_id: int | None = Query(default=None, gt=0),
    reason: str = Query(
        default="",
        max_length=MAX_AUDIT_REASON_CHARS,
        description="열람 사유 — 감사 로그에 기록",
    ),
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return get_admin_chats_page(
        db,
        user,
        filter_query=filter_query,
        limit=limit,
        user_id=user_id,
        thread_id=thread_id,
        status_=status_,
        before_id=before_id,
        reason=reason,
    )


@router.get(
    "/security/password-hashes",
    response_model=PasswordHashStatusOut,
    summary="비밀번호 해시 마이그레이션 현황",
    description=(
        "페퍼(p2:) 적용 해시와 레거시(페퍼 이전) 해시의 사용자 수를 보고한다. "
        "legacy가 0이 되면 verify_password_legacy 폴백을 제거해도 안전하다"
        "(docs/OPERATIONS.md '레거시 폴백 제거 기준' 참조)."
    ),
    responses={401: {"description": "로그인 필요"}, 403: {"description": "앱 관리자 권한 필요"}},
)
def password_hash_status(
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return get_password_hash_migration_status(db, user)


@router.delete(
    "/users/{user_id}",
    response_model=DeletedUserOut,
    summary="사용자 삭제(테스트 계정 정리 등)",
    description=(
        "관리자 전용. 대화 기록·세션 폐기 표시·재설정 토큰이 함께 삭제되고(FK CASCADE) "
        "해당 사용자의 서버 측 세션도 즉시 폐기한다. 자기 자신과 다른 관리자는 삭제할 수 없다."
    ),
    responses={
        400: {"description": "자기 자신 또는 다른 관리자 삭제 시도"},
        401: {"description": "로그인 필요"},
        403: {"description": "앱 관리자 권한 필요"},
        404: {"description": "존재하지 않는 사용자"},
    },
)
def delete_user(
    user_id: int,
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return delete_user_by_admin(db, user, user_id)


@router.get(
    "/stats",
    summary="관리자 대시보드 통계",
    description="사용자·스레드·대화·성공률·최근 24시간 요청/이벤트 수. 관리자 권한 필요.",
)
def stats(user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """사용자·스레드·대화·성공률·최근 24시간 요청 수를 집계한다."""
    return get_admin_dashboard_stats(db, user)


@router.get(
    "/events",
    response_model=AdminEventPage,
    summary="이벤트 로그 조회",
    description=(
        "감사 이벤트 DB 영속분을 최신순으로 반환한다. event로 이름 필터, "
        "before_id로 이전 페이지. 마스킹된 메타데이터만 담긴다(원문 질문·응답 제외)."
    ),
)
def all_events(
    filter_query: str = Query(default="", max_length=200, alias="filter"),
    event: str | None = Query(default=None, max_length=64),
    user_id: int | None = Query(default=None, gt=0),
    before_id: int | None = Query(default=None, gt=0),
    limit: int = DEFAULT_PAGE_SIZE,
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    search: str | None = None,
):
    return get_admin_events_page(
        db,
        user,
        filter_query=filter_query,
        event=event,
        user_id=user_id,
        before_id=before_id,
        limit=limit,
        search=search,
    )


@router.get(
    "/network",
    response_model=AdminRequestLogPage,
    summary="네트워크 로그 조회",
    description=(
        "/api/ 요청 기록(method·path·status·지연)을 최신순으로 반환한다. "
        "status로 상태코드 필터, before_id로 이전 페이지. 보존 한도는 5,000건."
    ),
)
def all_requests(
    filter_query: str = Query(default="", max_length=200, alias="filter"),
    status_: int | None = Query(default=None, alias="status"),
    before_id: int | None = Query(default=None, gt=0),
    limit: int = DEFAULT_PAGE_SIZE,
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    path: str | None = None,
    method: str | None = None,
    user_id: int | None = None,
):
    return get_admin_requests_page(
        db,
        user,
        filter_query=filter_query,
        status_=status_,
        before_id=before_id,
        limit=limit,
        path=path,
        method=method,
        user_id=user_id,
    )


@router.get(
    "/db/tables",
    response_model=list[AdminDbTableOut],
    summary="DB 테이블 목록·행수",
    description="앱이 소유한 테이블만 화이트리스트로 노출한다 — 임의 SQL은 없다.",
)
def db_tables(user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """앱이 소유한 테이블만 화이트리스트로 노출한다 — 임의 SQL은 없다."""
    return get_admin_db_tables(db, user)


@router.get(
    "/db/tables/{name}/rows",
    response_model=AdminDbRows,
    summary="DB 테이블 행 미리보기",
    description=(
        "화이트리스트 테이블의 최근 행을 id 내림차순으로 반환한다. "
        "읽기 전용이며 존재하지 않는 이름은 404."
    ),
)
def db_table_rows(
    name: str,
    before_id: int | None = Query(default=None, gt=0),
    limit: int = DEFAULT_PAGE_SIZE,
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """화이트리스트 테이블의 최근 행을 id 내림차순으로 반환 — 읽기 전용·임의 SQL 없음."""
    return get_admin_db_table_rows(db, user, name, before_id=before_id, limit=limit)


@router.get(
    "/suggest",
    summary="필터 값 자동완성 후보",
    description="관리자 콘솔 필터박스의 값 후보. 화이트리스트 밖 필드는 400.",
)
def suggest_values(
    field: str = Query(max_length=16, description="후보 종류 — 화이트리스트"),
    q: str = Query(default="", max_length=64, description="입력 중인 값"),
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """관리자 콘솔 필터박스의 값 후보. 화이트리스트 밖 필드는 400."""
    suggestor = SUGGESTORS.get(field)
    if suggestor is None:
        raise HTTPException(status_code=400, detail="지원하지 않는 필드예요.")
    clean = q.strip()[:64]
    items = suggestor(db, clean)
    return {"field": field, "items": items[:MAX_SUGGESTIONS]}
