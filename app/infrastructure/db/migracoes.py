"""Roda as migrações do Alembic por código (subida da API, CLI e testes)."""

from pathlib import Path

from alembic import command
from alembic.config import Config

RAIZ = Path(__file__).resolve().parents[3]


def config_alembic(database_url: str) -> Config:
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "alembic"))
    # O configparser trata "%" como interpolação; senhas com % precisam virar %%.
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return cfg


def migrar(database_url: str, revisao: str = "head") -> None:
    command.upgrade(config_alembic(database_url), revisao)


def reverter(database_url: str, revisao: str = "base") -> None:
    command.downgrade(config_alembic(database_url), revisao)
