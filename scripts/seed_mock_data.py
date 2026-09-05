#!/usr/bin/env python3
"""목데이터 시딩 — 평가/데모용 계정과 대화 로그를 DB에 생성한다.

사용법 (프로젝트 루트에서):
    python scripts/seed_mock_data.py            # 기본 DB(app.db)에 생성
    python scripts/seed_mock_data.py --fresh    # 기존 목데이터 삭제 후 재생성

생성되는 계정 (비밀번호 전부 Test1234!):
    demo@demo.com   (데모유저)  — 문맥 시연용 Q/A 3건
    tester@demo.com (테스터)    — 일반 대화 2건 + AI 타임아웃 실패 1건(status=ai_error)
    admin@demo.com  (운영자)    — 빈 계정 (로그인/권한 테스트용)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import ChatLog, User  # noqa: E402
from app.services.security import hash_password  # noqa: E402

MOCK_PASSWORD = "Test1234!"

MOCK_USERS = [
    {"email": "demo@demo.com", "nickname": "데모유저"},
    {"email": "tester@demo.com", "nickname": "테스터"},
    {"email": "admin@demo.com", "nickname": "운영자"},
]

MOCK_CHATS = {
    "demo@demo.com": [
        ("FastAPI로 배포하는 방법 알려줘",
         "uvicorn app.main:app --host 0.0.0.0 으로 실행하고, 플랫폼(Cloudtype/Render 등)의 "
         "환경변수에 AI_API_KEY 등을 설정하면 됩니다. 상세는 README 9번 섹션을 참고하세요.", 1240),
        ("내가 방금 뭘 물어봤지?",
         "직전에 'FastAPI로 배포하는 방법 알려줘'를 물어보셨고, uvicorn 실행 명령과 환경변수 설정을 안내드렸어요.",
         980),
        ("컨텍스트는 몇 턴까지 기억해?",
         "직전 5개의 질문/응답(CONTEXT_TURNS=5)을 프롬프트에 포함해 문맥을 유지합니다. .env에서 조절할 수 있어요.",
         1100),
    ],
    "tester@demo.com": [
        ("SQLite 로그 확인하는 법?",
         "sqlite3 app.db < scripts/check_logs.sql 로 최근 대화 로그를 조회할 수 있습니다.", 1050),
        ("타임아웃은 어떻게 되지?",
         "AI_TIMEOUT_SEC(기본 10초)를 초과하면 504와 함께 AI_TIMEOUT 안내가 반환됩니다.", 990),
        ("타임아웃 강제 발생 테스트", "", 2007),  # status=ai_error
    ],
    "admin@demo.com": [],
}


def seed(fresh: bool) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if fresh:
            deleted = db.query(ChatLog).delete()
            users_deleted = db.query(User).filter(
                User.email.in_([u["email"] for u in MOCK_USERS])).delete(synchronize_session=False)
            db.commit()
            print(f"🧹 기존 목데이터 삭제: 채팅 {deleted}건 / 사용자 {users_deleted}명")

        for info in MOCK_USERS:
            existing = db.query(User).filter(User.email == info["email"]).first()
            if existing:
                print(f"· {info['email']} 이미 존재 → 스킵")
                continue
            db.add(User(email=info["email"], password_hash=hash_password(MOCK_PASSWORD),
                        nickname=info["nickname"]))
        db.commit()

        for email, chats in MOCK_CHATS.items():
            user = db.query(User).filter(User.email == email).first()
            if not user:
                continue
            already = db.query(ChatLog).filter(ChatLog.user_id == user.id).count()
            if already:
                print(f"· {email} 대화로그 이미 {already}건 → 스킵")
                continue
            for i, (q, a, latency) in enumerate(chats):
                status = "ai_error" if a == "" else "success"
                db.add(ChatLog(user_id=user.id, question=q, answer=a,
                               latency_ms=latency, status=status, request_id=f"mock{i:02d}"))
            db.commit()
            print(f"✅ {email}: 대화 {len(chats)}건 생성")

        print("\n🎉 목데이터 시딩 완료 — 로그인: demo@demo.com / Test1234!")
        print("   확인: sqlite3 app.db < scripts/check_logs.sql")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh", action="store_true", help="기존 목데이터 삭제 후 재생성")
    args = parser.parse_args()
    seed(args.fresh)
