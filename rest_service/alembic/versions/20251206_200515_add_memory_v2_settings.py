"""Add Memory V2 settings to GlobalSettings

Revision ID: add_memory_v2_settings
Revises: 20251206_180000_cleanup_legacy_user_tables
Create Date: 2024-12-06

"""

from alembic import op
import sqlalchemy as sa


revision = "add_memory_v2_settings"
down_revision = "20251206_180000_cleanup_legacy_user_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Memory Extraction Settings
    op.add_column(
        "globalsettings",
        sa.Column(
            "memory_extraction_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "globalsettings",
        sa.Column(
            "memory_extraction_interval_hours",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("24"),
        ),
    )
    op.add_column(
        "globalsettings",
        sa.Column(
            "memory_extraction_model",
            sa.String(),
            nullable=False,
            server_default="gpt-4o-mini",
        ),
    )
    op.add_column(
        "globalsettings",
        sa.Column(
            "memory_extraction_provider",
            sa.String(),
            nullable=False,
            server_default="openai",
        ),
    )

    # Deduplication Settings
    op.add_column(
        "globalsettings",
        sa.Column(
            "memory_dedup_threshold",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.85"),
        ),
    )
    op.add_column(
        "globalsettings",
        sa.Column(
            "memory_update_threshold",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.95"),
        ),
    )

    # Embedding Settings
    op.add_column(
        "globalsettings",
        sa.Column(
            "embedding_model",
            sa.String(),
            nullable=False,
            server_default="text-embedding-3-small",
        ),
    )
    op.add_column(
        "globalsettings",
        sa.Column(
            "embedding_provider",
            sa.String(),
            nullable=False,
            server_default="openai",
        ),
    )

    # Limits
    op.add_column(
        "globalsettings",
        sa.Column(
            "max_memories_per_user",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1000"),
        ),
    )
    op.add_column(
        "globalsettings",
        sa.Column(
            "memory_retrieve_limit",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("5"),
        ),
    )
    op.add_column(
        "globalsettings",
        sa.Column(
            "memory_retrieve_threshold",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.6"),
        ),
    )


def downgrade() -> None:
    op.drop_column("globalsettings", "memory_retrieve_threshold")
    op.drop_column("globalsettings", "memory_retrieve_limit")
    op.drop_column("globalsettings", "max_memories_per_user")
    op.drop_column("globalsettings", "embedding_provider")
    op.drop_column("globalsettings", "embedding_model")
    op.drop_column("globalsettings", "memory_update_threshold")
    op.drop_column("globalsettings", "memory_dedup_threshold")
    op.drop_column("globalsettings", "memory_extraction_provider")
    op.drop_column("globalsettings", "memory_extraction_model")
    op.drop_column("globalsettings", "memory_extraction_interval_hours")
    op.drop_column("globalsettings", "memory_extraction_enabled")
