"""DB 모델 패키지 — 도메인별 파일로 분리하고 여기서 재노출한다(#150).

- base.py: 공용(utcnow) / user.py·thread.py·chat_log.py: 핵심 도메인
- session.py: 세션 폐기·관리자 권한 / password_reset.py: 재설정 토큰

`from app.models import User`처럼 기존 import 경로는 그대로 유지된다.
Alembic(env.py)도 `from app.models import Base`로 메타데이터를 얻는다.
새 모델 추가 절차: 도메인 파일을 만들고 아래 import에 반드시 추가한다 —
import되지 않은 모델은 create_all/autogenerate가 릴레이션을 찾지 못한다.
"""

from app.database import Base
from app.models.base import utcnow  # noqa: F401 (재노출 — 기존 `from app.models import utcnow` 호환)
from app.models.chat_log import ChatLog  # noqa: F401 (재노출용)
from app.models.password_reset import PasswordReset  # noqa: F401
from app.models.session import AdminGrant  # noqa: F401
from app.models.session import SessionRevocation  # noqa: F401
from app.models.thread import Thread  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = [
    "Base",
    "AdminGrant",
    "ChatLog",
    "PasswordReset",
    "SessionRevocation",
    "Thread",
    "User",
    "utcnow",
]
