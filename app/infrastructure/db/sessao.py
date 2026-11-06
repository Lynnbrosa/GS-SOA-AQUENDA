"""Conexão com o banco a partir de DATABASE_URL (SQLite na VM, PostgreSQL se o grupo quiser)."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


def criar_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    argumentos: dict = {"pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        argumentos["connect_args"] = {"check_same_thread": False}
        if url.database and url.database != ":memory:":
            Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, **argumentos)

    if url.get_backend_name() == "sqlite":
        @event.listens_for(engine, "connect")
        def _pragmas(conexao, _):  # pragma: no cover - configuração do driver
            cursor = conexao.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def criar_fabrica(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def sessao_por_requisicao(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    sessao = fabrica()
    try:
        yield sessao
    finally:
        sessao.close()
