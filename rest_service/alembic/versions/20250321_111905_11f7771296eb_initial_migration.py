"""Initial migration

Revision ID: 11f7771296eb
Revises:
Create Date: 2025-03-21 11:19:05.269325+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "11f7771296eb"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "assistant",
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_secretary", sa.Boolean(), nullable=False),
        sa.Column("model", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("instructions", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("assistant_type", sa.String(), nullable=True),
        sa.Column(
            "openai_assistant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assistant_is_active"), "assistant", ["is_active"], unique=False
    )
    op.create_index(
        op.f("ix_assistant_is_secretary"), "assistant", ["is_secretary"], unique=False
    )
    op.create_index(op.f("ix_assistant_name"), "assistant", ["name"], unique=False)
    op.create_index(
        op.f("ix_assistant_openai_assistant_id"),
        "assistant",
        ["openai_assistant_id"],
        unique=False,
    )
    op.create_table(
        "telegramuser",
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_table(
        "calendarcredentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("refresh_token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("token_expiry", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["telegramuser.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cronjob",
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("NOTIFICATION", "SCHEDULE", name="cronjobtype"),
            nullable=False,
        ),
        sa.Column(
            "cron_expression", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["telegramuser.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tool",
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("tool_type", sa.String(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("input_schema", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("assistant_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assistant_id"],
            ["assistant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tool_assistant_id"), "tool", ["assistant_id"], unique=False
    )
    op.create_index(op.f("ix_tool_is_active"), "tool", ["is_active"], unique=False)
    op.create_index(op.f("ix_tool_name"), "tool", ["name"], unique=False)
    op.create_table(
        "userassistantthread",
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("assistant_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("last_used", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assistant_id"],
            ["assistant.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_userassistantthread_assistant_id"),
        "userassistantthread",
        ["assistant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_userassistantthread_last_used"),
        "userassistantthread",
        ["last_used"],
        unique=False,
    )
    op.create_index(
        op.f("ix_userassistantthread_user_id"),
        "userassistantthread",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "usersecretarylink",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("secretary_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["secretary_id"],
            ["assistant.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["telegramuser.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "assistanttoollink",
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assistant_id", sa.Uuid(), nullable=False),
        sa.Column("tool_id", sa.Uuid(), nullable=False),
        sa.Column("sub_assistant_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assistant_id"],
            ["assistant.id"],
        ),
        sa.ForeignKeyConstraint(
            ["sub_assistant_id"],
            ["assistant.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tool_id"],
            ["tool.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assistanttoollink_assistant_id"),
        "assistanttoollink",
        ["assistant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistanttoollink_is_active"),
        "assistanttoollink",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistanttoollink_sub_assistant_id"),
        "assistanttoollink",
        ["sub_assistant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistanttoollink_tool_id"),
        "assistanttoollink",
        ["tool_id"],
        unique=False,
    )
    op.create_table(
        "cronjobnotification",
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cron_job_id", sa.Integer(), nullable=True),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cron_job_id"],
            ["cronjob.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cronjobrecord",
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cron_job_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("CREATED", "RUNNING", "DONE", "FAILED", name="cronjobstatus"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cron_job_id"],
            ["cronjob.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("cronjobrecord")
    op.drop_table("cronjobnotification")
    op.drop_index(op.f("ix_assistanttoollink_tool_id"), table_name="assistanttoollink")
    op.drop_index(
        op.f("ix_assistanttoollink_sub_assistant_id"), table_name="assistanttoollink"
    )
    op.drop_index(
        op.f("ix_assistanttoollink_is_active"), table_name="assistanttoollink"
    )
    op.drop_index(
        op.f("ix_assistanttoollink_assistant_id"), table_name="assistanttoollink"
    )
    op.drop_table("assistanttoollink")
    op.drop_table("usersecretarylink")
    op.drop_index(
        op.f("ix_userassistantthread_user_id"), table_name="userassistantthread"
    )
    op.drop_index(
        op.f("ix_userassistantthread_last_used"), table_name="userassistantthread"
    )
    op.drop_index(
        op.f("ix_userassistantthread_assistant_id"), table_name="userassistantthread"
    )
    op.drop_table("userassistantthread")
    op.drop_index(op.f("ix_tool_name"), table_name="tool")
    op.drop_index(op.f("ix_tool_is_active"), table_name="tool")
    op.drop_index(op.f("ix_tool_assistant_id"), table_name="tool")
    op.drop_table("tool")
    op.drop_table("cronjob")
    op.drop_table("calendarcredentials")
    op.drop_table("telegramuser")
    op.drop_index(op.f("ix_assistant_openai_assistant_id"), table_name="assistant")
    op.drop_index(op.f("ix_assistant_name"), table_name="assistant")
    op.drop_index(op.f("ix_assistant_is_secretary"), table_name="assistant")
    op.drop_index(op.f("ix_assistant_is_active"), table_name="assistant")
    op.drop_table("assistant")
    # ### end Alembic commands ###
