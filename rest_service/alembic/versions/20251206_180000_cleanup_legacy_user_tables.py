"""Cleanup legacy user_facts and user_summaries tables

Revision ID: cleanup_legacy_001
Revises: e9cc6eb00d30
Create Date: 2025-12-06 18:00:00

These tables are replaced by the unified Memory table (Memory V2).
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "cleanup_legacy_001"
down_revision = "e9cc6eb00d30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # First, drop FK constraint and column from messages table
    op.drop_constraint("messages_summary_id_fkey", "messages", type_="foreignkey")
    op.drop_column("messages", "summary_id")
    
    # Drop user_summaries table (replaced by Memory V2)
    op.drop_table("user_summaries")
    
    # Drop user_facts table (replaced by Memory V2)
    op.drop_table("user_facts")


def downgrade() -> None:
    # Recreate user_facts table
    op.execute("""
        CREATE TABLE user_facts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id INTEGER NOT NULL REFERENCES telegramuser(id),
            fact TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.create_index("ix_user_facts_user_id", "user_facts", ["user_id"])
    
    # Recreate user_summaries table
    op.execute("""
        CREATE TABLE user_summaries (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES telegramuser(id),
            assistant_id UUID NOT NULL REFERENCES assistant(id),
            summary_text TEXT NOT NULL,
            token_count INTEGER,
            last_message_id_covered INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.create_index("ix_user_summaries_user_id", "user_summaries", ["user_id"])
    op.create_index("ix_user_summaries_assistant_id", "user_summaries", ["assistant_id"])
    
    # Add summary_id column back to messages
    op.add_column("messages", sa.Column("summary_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "messages_summary_id_fkey", "messages", "user_summaries",
        ["summary_id"], ["id"]
    )
