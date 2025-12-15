"""Add job_executions table for cron job monitoring.

Revision ID: add_job_executions
Revises: fix_memories_tz
Create Date: 2025-12-14 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "add_job_executions"
down_revision: str | None = "fix_memories_tz"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("job_name", sa.String(), nullable=False),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("scheduled_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("reminder_id", sa.Integer(), nullable=True),
        sa.Column("result", sa.TEXT(), nullable=True),
        sa.Column("error", sa.TEXT(), nullable=True),
        sa.Column("error_traceback", sa.TEXT(), nullable=True),
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
        op.f("ix_job_executions_job_id"), "job_executions", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_job_executions_job_type"), "job_executions", ["job_type"], unique=False
    )
    op.create_index(
        op.f("ix_job_executions_status"), "job_executions", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_job_executions_user_id"), "job_executions", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_job_executions_user_id"), table_name="job_executions")
    op.drop_index(op.f("ix_job_executions_status"), table_name="job_executions")
    op.drop_index(op.f("ix_job_executions_job_type"), table_name="job_executions")
    op.drop_index(op.f("ix_job_executions_job_id"), table_name="job_executions")
    op.drop_table("job_executions")
