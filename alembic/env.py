"""Alembic lê DATABASE_URL do ambiente (ou do .env), a mesma variável da API."""

import logging
from logging.config import fileConfig

from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from app.config import Settings
from app.infrastructure.db.modelos import Base

config = context.config

# Pela linha de comando, configura o log do alembic.ini. Por código (API/testes), não mexe no log de quem chamou.
if config.config_file_name and not logging.getLogger().handlers:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", Settings().database_url.replace("%", "%%"))

target_metadata = Base.metadata


def _criar_pasta_do_sqlite(url: str) -> None:
    """Na VM o banco fica em /var/lib/aquenda/; a pasta pode ainda não existir."""
    destino = make_url(url)
    if destino.get_backend_name() == "sqlite" and destino.database and destino.database != ":memory:":
        Path(destino.database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _criar_pasta_do_sqlite(config.get_main_option("sqlalchemy.url"))
    conectavel = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.",
                                    poolclass=pool.NullPool)
    with conectavel.connect() as conexao:
        # render_as_batch: o SQLite não tem ALTER COLUMN; o Alembic recria a tabela quando precisa.
        context.configure(connection=conexao, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
