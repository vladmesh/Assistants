"""Add checkpoint table

Revision ID: 2dd537c210c1
Revises: 13efde9c4370
Create Date: 2025-04-12 18:25:58.383303+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2dd537c210c1"
down_revision: Union[str, None] = "13efde9c4370"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "checkpoints",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("checkpoint_blob", sa.LargeBinary(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_checkpoints_id"), "checkpoints", ["id"], unique=True)
    op.create_index(
        op.f("ix_checkpoints_thread_id"), "checkpoints", ["thread_id"], unique=False
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_checkpoints_thread_id"), table_name="checkpoints")
    op.drop_index(op.f("ix_checkpoints_id"), table_name="checkpoints")
    op.drop_table("checkpoints")
    # ### end Alembic commands ###
