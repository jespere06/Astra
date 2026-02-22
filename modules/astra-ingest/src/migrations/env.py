import sys
import os
from logging.config import fileConfig
# IMPORTANTE: Asegúrate de tener 'create_engine' aquí:
from sqlalchemy import engine_from_config, pool, create_engine 
from alembic import context

# --- CONFIGURACIÓN DE RUTAS ---
sys.path.append(os.getcwd())
from src.config import settings
from src.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = settings.DATABASE_URL # Usamos nuestra config de Python
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    # MODIFICACIÓN AQUÍ: 
    # En lugar de engine_from_config, creamos el engine manualmente
    connectable = create_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()