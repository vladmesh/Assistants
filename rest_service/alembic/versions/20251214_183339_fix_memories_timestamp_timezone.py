"""Fix memories table timestamp columns to use timezone

Revision ID: fix_memories_tz
Revises: a1b2c3d4e5f6
Create Date: 2025-12-14 18:33:39

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "fix_memories_tz"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter timestamp columns to use timezone
    # PostgreSQL will convert existing values assuming they are in UTC
    op.execute(
        """
        ALTER TABLE memories
        ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE
            USING created_at AT TIME ZONE 'UTC',
        ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE
            USING updated_at AT TIME ZONE 'UTC',
        ALTER COLUMN last_accessed_at TYPE TIMESTAMP WITH TIME ZONE
            USING last_accessed_at AT TIME ZONE 'UTC'
        """
    )


def downgrade() -> None:
    # Revert to timestamp without timezone
    op.execute(
        """
        ALTER TABLE memories
        ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE,
        ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE,
        ALTER COLUMN last_accessed_at TYPE TIMESTAMP WITHOUT TIME ZONE
        """
    )
