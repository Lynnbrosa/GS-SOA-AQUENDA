"""Migrações: sobem do zero, descem até o fim e batem com os modelos."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.infrastructure.db.migracoes import migrar, reverter
from app.infrastructure.db.modelos import Base

TABELAS = {"vagas", "municipios", "estabelecimentos_cnes", "habilitacoes_cnes", "sincronizacoes"}


def test_upgrade_cria_tabelas_e_dados_curados(settings):
    migrar(settings.database_url)
    engine = create_engine(settings.database_url)
    assert TABELAS <= set(inspect(engine).get_table_names())
    with engine.connect() as c:
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        assert c.scalar(text("SELECT count(*) FROM vagas WHERE origem = 'curadoria'")) == 2
        assert c.scalar(text("SELECT codigo FROM habilitacoes_cnes WHERE codigo_cnes = 2078015")) == "30.02"


def test_modelos_e_migracoes_nao_divergem(settings):
    migrar(settings.database_url)
    engine = create_engine(settings.database_url)
    with engine.connect() as c:
        diferencas = compare_metadata(MigrationContext.configure(c), Base.metadata)
    assert diferencas == [], f"Falta migração para: {diferencas}"


def test_downgrade_desfaz_tudo_e_upgrade_de_novo_funciona(settings):
    migrar(settings.database_url)
    reverter(settings.database_url, "0001")
    engine = create_engine(settings.database_url)
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM vagas")) == 0
    reverter(settings.database_url, "base")
    assert TABELAS.isdisjoint(inspect(engine).get_table_names())
    migrar(settings.database_url)
    assert TABELAS <= set(inspect(create_engine(settings.database_url)).get_table_names())
