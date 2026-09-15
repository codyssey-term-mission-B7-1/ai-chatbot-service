"""admin console: audit_events + request_logs

Revision ID: f3c8a2e91b47
Revises: b11425f8d01f
Create Date: 2026-09-15

"""

from typing import Sequence, Union

import app.models  # noqa: F401 — 모델 레지스트리 로드
from alembic import op
from sqlalchemy import DateTime, Integer, String, Text

# revision identifiers, used by Alembic.
revision: str = "f3c8a2e91b47"
down_revision: Union[str, None] = "b11425f8d01f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """관리자 콘솔용 이벤트·네트워크 로그 테이블 신설(#189)."""
    from app.models import AuditEvent, RequestLog

    AuditEvent.__table__.create(bind=op.get_bind(), checkfirst=True)
    RequestLog.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    from app.models import AuditEvent, RequestLog

    RequestLog.__table__.drop(bind=op.get_bind(), checkfirst=True)
    AuditEvent.__table__.drop(bind=op.get_bind(), checkfirst=True)
