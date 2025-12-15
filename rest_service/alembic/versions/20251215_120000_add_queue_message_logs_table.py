"""Add queue_message_logs table for Redis queue observability.

Revision ID: add_queue_message_logs
Revises: add_job_executions
Create Date: 2025-12-15 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "add_queue_message_logs"
down_revision: str | None = "add_job_executions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "queue_message_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("queue_name", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("payload", sa.TEXT(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_queue_message_logs_queue_name"),
        "queue_message_logs",
        ["queue_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_queue_message_logs_correlation_id"),
        "queue_message_logs",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_queue_message_logs_user_id"),
        "queue_message_logs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_queue_message_logs_user_id"), table_name="queue_message_logs"
    )
    op.drop_index(
        op.f("ix_queue_message_logs_correlation_id"), table_name="queue_message_logs"
    )
    op.drop_index(
        op.f("ix_queue_message_logs_queue_name"), table_name="queue_message_logs"
    )
    op.drop_table("queue_message_logs")
