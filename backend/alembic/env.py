from logging.config import fileConfig
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add /app to path if not already there
if '/app' not in sys.path:
    sys.path.insert(0, '/app')

try:
    from app.core.config import get_settings
    from app.db.base import Base
    from app.models import *  # noqa: F401,F403
    settings = get_settings()
    db_url = settings.database_url
    target_metadata = Base.metadata
except ImportError:
    # Fallback for alembic CLI without proper env setup
    db_url = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:postgres@db:5432/judiciary_accountability')
    target_metadata = None

config = context.config
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
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
