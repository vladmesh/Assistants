"""Remove OpenAI Assistants API legacy: openai_assistant_id column and user_assistant_threads table

Revision ID: 77a177d0696a
Revises: a2b961b9ad17
Create Date: 2025-12-05 23:04:38.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '77a177d0696a'
down_revision: Union[str, None] = 'a2b961b9ad17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get database connection to check what exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Drop openai_assistant_id column and its index from assistant table (if exists)
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('assistant')]
    if 'ix_assistant_openai_assistant_id' in existing_indexes:
        op.drop_index('ix_assistant_openai_assistant_id', table_name='assistant')
    
    existing_columns = [col['name'] for col in inspector.get_columns('assistant')]
    if 'openai_assistant_id' in existing_columns:
        op.drop_column('assistant', 'openai_assistant_id')
    
    # Drop user_assistant_threads table if it exists
    existing_tables = inspector.get_table_names()
    if 'user_assistant_threads' in existing_tables:
        op.drop_table('user_assistant_threads')


def downgrade() -> None:
    # Recreate user_assistant_threads table
    op.create_table(
        'user_assistant_threads',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('assistant_id', sa.UUID(), nullable=False),
        sa.Column('thread_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('last_used', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assistant_id'], ['assistant.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_assistant_threads_user_id', 'user_assistant_threads', ['user_id'], unique=False)
    op.create_index('ix_user_assistant_threads_assistant_id', 'user_assistant_threads', ['assistant_id'], unique=False)
    op.create_index('ix_user_assistant_threads_last_used', 'user_assistant_threads', ['last_used'], unique=False)
    
    # Recreate openai_assistant_id column in assistant table
    op.add_column('assistant', sa.Column('openai_assistant_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_index('ix_assistant_openai_assistant_id', 'assistant', ['openai_assistant_id'], unique=False)
