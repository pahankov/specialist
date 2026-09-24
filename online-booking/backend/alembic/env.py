"""Alembic environment configuration."""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text, MetaData

from alembic import context

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base
from app.config import settings

# Import all models so Alembic can detect them
from app.models.user import User  # noqa: F401
from app.models.master_profile import MasterProfile  # noqa: F401
from app.models.client_profile import ClientProfile  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.appointment import Appointment  # noqa: F401
from app.models.working_hour import WorkingHour  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.blocked_slot import BlockedSlot  # noqa: F401
from app.models.country import Country  # noqa: F401
from app.models.city import City  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.otp_code import OtpCode  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Use URL from alembic.ini (sync sqlite:///, not aiosqlite:///)
# Do NOT override with settings.DATABASE_URL (that's async)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,  # For SQLite compatibility
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # For SQLite compatibility
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
