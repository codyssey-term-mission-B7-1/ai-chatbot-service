"""add db check constraints

Revision ID: b11425f8d01f
Revises: c7e4a9b21d05
Create Date: 2026-09-15 11:56:51.848395+09:00

"""

from typing import Sequence, Union

import app.models  # noqa: F401 — 모델 레지스트리 로드
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "b11425f8d01f"
down_revision: Union[str, None] = "c7e4a9b21d05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# batch 재생성 대상 테이블 — 인덱스는 alembic batch가 복사하지 않으므로 직접 재생성한다
_TABLES = "users", "threads", "chat_logs"


def _recreate_indexes() -> None:
    from app.models import ChatLog, Thread, User

    bind = op.get_bind()
    for table in (User.__table__, Thread.__table__, ChatLog.__table__):
        for index in table.indexes:
            index.create(bind=bind)


def _rebuild_add_checks() -> None:
    from app.models import ChatLog, Thread, User
    from app.policies import QUESTION_ABS_MAX_CHARS

    with op.batch_alter_table("users", copy_from=User.__table__) as batch_op:
        batch_op.create_check_constraint(
            "ck_users_email_length", "length(email) BETWEEN 3 AND 255"
        )
        batch_op.create_check_constraint(
            "ck_users_nickname_length", "length(nickname) BETWEEN 1 AND 50"
        )
    with op.batch_alter_table("threads", copy_from=Thread.__table__) as batch_op:
        batch_op.create_check_constraint(
            "ck_threads_title_length", "title IS NULL OR length(title) <= 60"
        )
    with op.batch_alter_table("chat_logs", copy_from=ChatLog.__table__) as batch_op:
        batch_op.create_check_constraint(
            "ck_chat_logs_status", "status IN ('success', 'ai_error')"
        )
        batch_op.create_check_constraint(
            "ck_chat_logs_question_length",
            "length(trim(question)) BETWEEN 1 AND " + str(QUESTION_ABS_MAX_CHARS),
        )


def upgrade() -> None:
    """기존 테이블을 재생성(batch)해 CHECK 제약을 부여한다 — 4층 방어의 DB 층(#183).

    FK를 켠 채 부모 테이블을 DROP하면 SQLite의 암시적 DELETE가 CASCADE로
    자식 데이터를 증발시키므로, batch 전후로 FK를 껐다 켠다.
    """
    op.execute(text("PRAGMA foreign_keys=OFF"))
    _rebuild_add_checks()
    _recreate_indexes()
    op.execute(text("PRAGMA foreign_keys=ON"))


def downgrade() -> None:
    from app.models import ChatLog, Thread, User

    op.execute(text("PRAGMA foreign_keys=OFF"))
    with op.batch_alter_table("chat_logs", copy_from=ChatLog.__table__) as batch_op:
        batch_op.drop_constraint("ck_chat_logs_question_length", type_="check")
        batch_op.drop_constraint("ck_chat_logs_status", type_="check")
    with op.batch_alter_table("threads", copy_from=Thread.__table__) as batch_op:
        batch_op.drop_constraint("ck_threads_title_length", type_="check")
    with op.batch_alter_table("users", copy_from=User.__table__) as batch_op:
        batch_op.drop_constraint("ck_users_nickname_length", type_="check")
        batch_op.drop_constraint("ck_users_email_length", type_="check")
    _recreate_indexes()
    op.execute(text("PRAGMA foreign_keys=ON"))
