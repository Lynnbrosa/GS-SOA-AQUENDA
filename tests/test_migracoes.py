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
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
        assert c.scalar(text("SELECT count(*) FROM vagas WHERE origem = 'curadoria'")) == 2
        habilitacoes = c.execute(text("SELECT codigo_cnes, codigo FROM habilitacoes_cnes ORDER BY codigo_cnes")).all()
        assert len(habilitacoes) == 9 and (2812703, "30.01") not in [tuple(h) for h in habilitacoes]
        assert "HBSP2609" in c.scalar(text("SELECT fonte FROM habilitacoes_cnes WHERE codigo_cnes = 2077957"))
        assert "PT GM 3231" in c.scalar(text("SELECT fonte FROM habilitacoes_cnes WHERE codigo_cnes = 2077957"))


def test_modelos_e_migracoes_nao_divergem(settings):
    migrar(settings.database_url)
    engine = create_engine(settings.database_url)
    with engine.connect() as c:
        diferencas = compare_metadata(MigrationContext.configure(c), Base.metadata)
    assert diferencas == [], f"Falta migração para: {diferencas}"


def test_downgrade_desfaz_tudo_e_upgrade_de_novo_funciona(settings):
    migrar(settings.database_url)
    reverter(settings.database_url, "0003")
    with create_engine(settings.database_url).connect() as c:
        assert c.scalar(text("SELECT count(*) FROM habilitacoes_cnes")) == 2, "0004 volta para a lista da portaria"
    reverter(settings.database_url, "0002")
    engine = create_engine(settings.database_url)
    with engine.connect() as c:
        assert c.scalar(text("SELECT codigo FROM habilitacoes_cnes")) == "30.02", "0003 desfaz a correção"
    reverter(settings.database_url, "0001")
    engine = create_engine(settings.database_url)
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM vagas")) == 0
    reverter(settings.database_url, "base")
    assert TABELAS.isdisjoint(inspect(engine).get_table_names())
    migrar(settings.database_url)
    assert TABELAS <= set(inspect(create_engine(settings.database_url)).get_table_names())
