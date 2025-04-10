import sys

# Assume the source code is mounted at /src in the container
# Explicitly add /src to the Python path
if "/src" not in sys.path:
    sys.path.insert(0, "/src")

import logging
import os
from logging.config import fileConfig

# from sqlmodel import SQLModel # Assuming models uses Base now
import models  # Use direct import since /src is in sys.path
from alembic import context
from sqlalchemy import engine_from_config, pool

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Импортируем все модели из пакета models

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = models.BaseModel.metadata

# Логируем все таблицы, которые видит SQLAlchemy
logger.info("Available tables:")
for table in target_metadata.tables:
    logger.info(f"- {table}")

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """Get database URL from environment variable."""
    # Read ASYNC_DATABASE_URL to match docker-compose.yml environment
    url = os.getenv("ASYNC_DATABASE_URL")
    if not url:
        # Update error message as well
        raise ValueError("ASYNC_DATABASE_URL environment variable is not set")
    # Заменяем asyncpg на psycopg2 для синхронных миграций Alembic
    sync_url = url.replace("+asyncpg", "")
    logger.info(f"Using database URL for Alembic: {sync_url}")
    return sync_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
