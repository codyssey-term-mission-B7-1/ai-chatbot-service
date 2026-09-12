#!/usr/bin/env python3
"""신뢰된 서버 운영자용 관리자 권한 관리. HTTP에서 호출하거나 공개하지 않는다."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['grant', 'revoke', 'list'])
    parser.add_argument('--email', help='이미 생성된 전용 관리자 계정의 이메일')
    args = parser.parse_args(argv)
    if args.operation != 'list' and not args.email:
        parser.error('grant/revoke에는 --email이 필요합니다')
    from app.database import SessionLocal, init_db
    from app.models import AdminGrant
    from app.services.admin import grant_admin, revoke_admin

    import app.models  # noqa: F401 — metadata 등록 보장
    init_db()
    with SessionLocal() as db:
        try:
            if args.operation == 'grant':
                user = grant_admin(db, args.email)
                print(f'관리자 권한 부여 완료: user_id={user.id}')
            elif args.operation == 'revoke':
                print('권한 회수 완료' if revoke_admin(db, args.email) else '해당 권한 없음')
            else:
                for row in db.query(AdminGrant).order_by(AdminGrant.user_id):
                    print(f'user_id={row.user_id} granted_email={row.granted_email}')
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
