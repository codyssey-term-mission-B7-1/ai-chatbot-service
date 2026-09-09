#!/usr/bin/env python3
"""신뢰된 서버 운영자용 세션 폐기. HTTP에서 호출하거나 공개하지 않는다.

계정 침해 대응·퇴장 등으로 특정 계정의 기존 로그인 세션을 모두 무효화한다.
폐기 이후 해당 계정은 재로그인하면 정상 이용할 수 있다.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="세션을 폐기할 계정의 이메일")
    args = parser.parse_args(argv)
    from app.database import Base, SessionLocal, engine
    from app.services.sessions import revoke_sessions_by_email

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        try:
            user = revoke_sessions_by_email(db, args.email)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"세션 폐기 완료: user_id={user.id} email={user.email}")
        print("해당 계정은 재로그인하면 정상 이용할 수 있습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
