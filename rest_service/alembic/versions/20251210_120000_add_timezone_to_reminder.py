"""Add timezone to reminders

Revision ID: add_timezone_to_reminder
Revises: add_memory_v2_settings
Create Date: 2025-12-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_timezone_to_reminder"
down_revision = "add_memory_v2_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reminders",
        sa.Column("timezone", sa.String(), nullable=True),
    )
    op.create_index(op.f("ix_reminders_timezone"), "reminders", ["timezone"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reminders_timezone"), table_name="reminders")
    op.drop_column("reminders", "timezone")
