from app.db.config import settings
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.db.base_class import Base
import app.models  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config


def get_url():
    return settings.DB_URL


config.set_main_option("sqlalchemy.url", get_url())

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.



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


def process_revision_directives(context, revision, directives):
    """Prevent empty migrations from being created."""
    if not directives:
        return

    script = directives[0]
    # Check if the migration is empty (no upgrade operations)
    # An empty migration has no ops in upgrade_ops
    upgrade_ops = getattr(script, "upgrade_ops", None)

    # Check if there are any operations
    has_operations = False
    if upgrade_ops is not None:
        ops = getattr(upgrade_ops, "ops", [])
        has_operations = len(ops) > 0

    # If no operations, skip creating the migration file
    if not has_operations:
        directives[:] = []
        print("No changes detected. Skipping empty migration.")


def run_migrations_online() -> None:
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
