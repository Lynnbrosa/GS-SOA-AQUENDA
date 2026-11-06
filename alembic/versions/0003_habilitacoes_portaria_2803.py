"""Habilitações do processo transexualizador conferidas na Portaria GM/MS nº 2.803/2013.

A 0002 marcou o HC-FMUSP como 30.02 sem fonte primária. O texto da portaria
(art. 9º, parágrafo único, alterado pela PRT 629/2014) lista em São Paulo:

- 2078015 HC da FMUSP ............................ 30.01
- 2812703 HCFMUSP, Instituto de Psiquiatria (IPq) .. 30.01

30.01 é o código de 2008 ("Unidade de Atenção Especializada"), que segue válido (art. 9º,
alterado pela PRT 2.736/2014). 30.02 é o ambulatorial e 30.03 o hospitalar.
Habilitações posteriores em SP entram pelo script scripts/habilitacoes_cnes.py,
que lê o arquivo oficial de habilitações do CNES (DATASUS).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-06
"""
from collections.abc import Sequence
from datetime import UTC, date, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PORTARIA = (
    "Portaria GM/MS nº 2.803/2013, art. 9º, parágrafo único (alterado pela PRT 629/2014) "
    "(https://bvsms.saude.gov.br/bvs/saudelegis/gm/2013/prt2803_19_11_2013.html)"
)
DESCRICAO = "Unidade de Atenção Especializada no Processo Transexualizador"
VERIFICADO = date(2026, 11, 6)
COLETA = datetime(2026, 11, 6, 4, 20, tzinfo=UTC).replace(tzinfo=None)

# Retrato da resposta real de GET /cnes/estabelecimentos/2812703 (sem o e-mail).
IPQ = {
    "codigo_cnes": 2812703,
    "nome": "FUNDACAO FACULDADE DE MEDICINAHCFMUSP INST DE PSIQUIATRIA SP",
    "razao_social": "FUNDACAO FACULDADE DE MEDICINA MECMPAS",
    "codigo_municipio": 355030,
    "logradouro": "RUA DR OVIDIO PIRES DE CAMPOS",
    "numero": "785",
    "bairro": "CERQUEIRA CESAR",
    "cep": "05403000",
    "telefone": "(11)3087-5456",
    "latitude": -23.558007796770593,
    "longitude": -46.67438507080078,
    "tipo_unidade": 7,
    "atende_sus": True,
    "turno": "ATENDIMENTO CONTINUO DE 24 HORAS/DIA (PLANTAO:INCLUI SABADOS, DOMINGOS E FERIADOS)",
    "atualizado_no_cnes": date(2025, 9, 3),
    "fonte": "CNES/DATASUS (https://apidadosabertos.saude.gov.br/cnes/estabelecimentos/2812703)",
    "coletado_em": COLETA,
}


def upgrade() -> None:
    conexao = op.get_bind()
    meta = sa.MetaData()
    habilitacoes = sa.Table("habilitacoes_cnes", meta, autoload_with=conexao)
    estabelecimentos = sa.Table("estabelecimentos_cnes", meta, autoload_with=conexao)

    conexao.execute(
        habilitacoes.update()
        .where(habilitacoes.c.codigo_cnes == 2078015, habilitacoes.c.codigo == "30.02")
        .values(codigo="30.01", descricao=DESCRICAO, fonte=PORTARIA, verificado_em=VERIFICADO)
    )
    if conexao.execute(sa.select(estabelecimentos.c.codigo_cnes).where(estabelecimentos.c.codigo_cnes == 2812703)).first() is None:
        op.bulk_insert(estabelecimentos, [IPQ])
    op.bulk_insert(habilitacoes, [{
        "codigo_cnes": 2812703, "codigo": "30.01", "descricao": DESCRICAO, "fonte": PORTARIA, "verificado_em": VERIFICADO,
    }])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM habilitacoes_cnes WHERE codigo_cnes = 2812703 AND codigo = '30.01'"))
    op.execute(sa.text("DELETE FROM estabelecimentos_cnes WHERE codigo_cnes = 2812703"))
    op.execute(sa.text(
        "UPDATE habilitacoes_cnes SET codigo = '30.02', descricao = 'Processo transexualizador' "
        "WHERE codigo_cnes = 2078015 AND codigo = '30.01'"
    ))
