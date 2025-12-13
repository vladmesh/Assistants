"""Add batch_jobs table for memory extraction tracking.

Revision ID: a1b2c3d4e5f6
Revises: 20251210_120000_add_timezone_to_reminder
Create Date: 2024-12-10 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "add_timezone_to_reminder"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "batch_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("assistant_id", sa.Uuid(), nullable=True),
        sa.Column("job_type", sa.String(), nullable=False, server_default="memory_extraction"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(), nullable=False, server_default="openai"),
        sa.Column("model", sa.String(), nullable=False, server_default="gpt-4o-mini"),
        sa.Column("messages_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("facts_extracted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.TEXT(), nullable=True),
        sa.Column("since_timestamp", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("until_timestamp", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["telegramuser.id"]),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistant.id"]),
    )
    op.create_index(
        op.f("ix_batch_jobs_batch_id"), "batch_jobs", ["batch_id"], unique=False
    )
    op.create_index(
        op.f("ix_batch_jobs_user_id"), "batch_jobs", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_batch_jobs_assistant_id"), "batch_jobs", ["assistant_id"], unique=False
    )
    op.create_index(
        op.f("ix_batch_jobs_status"), "batch_jobs", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_batch_jobs_job_type"), "batch_jobs", ["job_type"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_batch_jobs_job_type"), table_name="batch_jobs")
    op.drop_index(op.f("ix_batch_jobs_status"), table_name="batch_jobs")
    op.drop_index(op.f("ix_batch_jobs_assistant_id"), table_name="batch_jobs")
    op.drop_index(op.f("ix_batch_jobs_user_id"), table_name="batch_jobs")
    op.drop_index(op.f("ix_batch_jobs_batch_id"), table_name="batch_jobs")
    op.drop_table("batch_jobs")
