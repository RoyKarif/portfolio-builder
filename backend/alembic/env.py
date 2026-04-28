"""Alembic migration environment.

This file is the entrypoint Alembic runs whenever you do
`alembic upgrade head` or `alembic revision --autogenerate`. Its job:
    1. Configure the SQLAlchemy URL (from our app config).
    2. Tell Alembic which Base.metadata to inspect (so autogenerate
       can detect schema changes).
    3. Define how to run migrations in 'online' (live DB) and 'offline'
       (SQL-script-only) modes.

Alembic generates a default version of this file via `alembic init`;
this is a customized version that reads DATABASE_URL from app.config
and imports our models so autogenerate sees them.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Make `app` importable when alembic runs from the backend/ directory.
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.db import Base           # noqa: E402

# Importing the models registers them on Base.metadata. Without this,
# autogenerate sees no tables and produces empty migrations.
# (Will be uncommented in Step 3 when models exist.)
# from app.models import user, asset, price, portfolio  # noqa: F401, E402


# Alembic Config object — provides access to alembic.ini values.
config = context.config

# Inject the DATABASE_URL from our settings, overriding the empty value
# in alembic.ini. This way the DB URL is sourced from .env, not duplicated.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Configure Python logging from alembic.ini's [loggers] sections.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# What metadata to compare against the live DB. Base.metadata sees all
# models that inherit from Base — provided they were imported above.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL to stdout, no DB connect.

    Useful for generating SQL scripts for DBAs to review or run manually.
    Not used in our normal workflow but included for completeness.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the DB and applies.

    This is what `make migrate` triggers via `alembic upgrade head`.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


# Dispatch on the mode Alembic was invoked with.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
