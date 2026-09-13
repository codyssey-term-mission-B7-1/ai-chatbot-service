"""threads: 대화 스레드(새 채팅) + chat_logs.thread_id + 레거시 백필

Revision ID: c7e4a9b21d05
Revises: 9dea740a4bf1
Create Date: 2026-09-13 00:00:00.000000+09:00

- threads 테이블 생성(user별, title은 첫 질문에서 자동 생성 — NULL 허용)
- 기존 사용자마다 '기본 대화' 스레드를 만들고 기존 chat_logs를 그 스레드에 귀속한다
  (데이터 보존 — 기존 대화는 삭제되지 않고 '기본 대화'로 보여진다)
- chat_logs.thread_id는 NULL 허용 후 FK 적용(레거시 행이 NULL로 남아도 안전,
  백필이 정상 실행되면 모든 행이 귀속된다)
- SQLite ALTER 제약 때문에 chat_logs 열 추가/FK는 batch_alter_table 사용
"""

from typing import Sequence, Union

import sqlalchemy as sa
from datetime import datetime, timezone

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e4a9b21d05"
down_revision: Union[str, Sequence[str], None] = "9dea740a4bf1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "threads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_threads_user_id"), "threads", ["user_id"], unique=False)

    # 기존 사용자마다 '기본 대화' 스레드 생성 — ORM이 쓰는 시각 포맷과 일치하도록
    # 매개변수로 전달(SQLAlchemy bind 프로세서가 동일 형식으로 저장).
    now = datetime.now(timezone.utc)
    op.execute(
        sa.text(
            "INSERT INTO threads (user_id, title, created_at, updated_at) "
            "SELECT id, :title, :now, :now FROM users"
        ).bindparams(title="기본 대화", now=now)
    )

    with op.batch_alter_table("chat_logs") as batch:
        batch.add_column(sa.Column("thread_id", sa.Integer(), nullable=True))

    # 레거시 기록을 해당 사용자의 기본 대화에 귀속
    op.execute(
        sa.text(
            "UPDATE chat_logs SET thread_id = "
            "(SELECT t.id FROM threads t WHERE t.user_id = chat_logs.user_id)"
        )
    )

    with op.batch_alter_table("chat_logs") as batch:
        batch.create_foreign_key(
            "fk_chat_logs_thread_id_threads", "threads", ["thread_id"], ["id"],
            ondelete="CASCADE",
        )
    op.create_index(op.f("ix_chat_logs_thread_id"), "chat_logs", ["thread_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_logs_thread_id"), table_name="chat_logs")
    with op.batch_alter_table("chat_logs") as batch:
        batch.drop_constraint("fk_chat_logs_thread_id_threads", type_="foreignkey")
        batch.drop_column("thread_id")
    op.drop_index(op.f("ix_threads_user_id"), table_name="threads")
    op.drop_table("threads")
