"""Add is_active field to CronJob

Revision ID: b201a35b7385
Revises: 11f7771296eb
Create Date: 2025-03-21 12:25:12.220885+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b201a35b7385"
down_revision: Union[str, None] = "11f7771296eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("cronjob", sa.Column("is_active", sa.Boolean(), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("cronjob", "is_active")
    # ### end Alembic commands ###
