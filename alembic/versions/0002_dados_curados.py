"""Dados curados pelo grupo: vagas fixas, lista de habilitação 30.02 e um ponto de partida offline.

- Transcidadania e TransEmpregos entram como vagas da curadoria, com fonte.
- A API aberta do CNES não filtra por habilitação. A lista de quem tem a 30.02
  (processo transexualizador) vem da curadoria; o sync completa o resto pelo CNES.
- Município de São Paulo e o retrato do HC-FMUSP coletado no CNES em 06/11/2026,
  para o app ter resposta antes da primeira sincronização (e na VM sem internet).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-06
"""
import re
import unicodedata
from collections.abc import Sequence
from datetime import UTC, date, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLETA = datetime(2026, 11, 6, 3, 25, tzinfo=UTC).replace(tzinfo=None)  # UTC sem fuso, como o resto do banco
VERIFICADO = date(2026, 11, 6)

FONTE_HABILITACAO = (
    "Curadoria do grupo a partir da portaria de habilitação do processo transexualizador "
    "(https://www.conass.org.br/?p=2674); conferir antes de publicar"
)


def _normalizar(texto: str | None) -> str:
    """Cópia local da regra do domínio: migração não importa código da aplicação."""
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


VAGAS = [
    {
        "id_externo": "transcidadania",
        "titulo": "Transcidadania · Prefeitura de São Paulo",
        "empresa": "Prefeitura de São Paulo",
        "descricao": (
            "Programa de reintegração social e resgate da cidadania para pessoas trans e travestis em "
            "vulnerabilidade. Auxílio de R$ 1.702,05 com 30 horas semanais de atividades. Em 2026 são 750 vagas. "
            "A inscrição é feita presencialmente nos Centros de Referência LGBTI+."
        ),
        "cidade": "São Paulo",
        "uf": "SP",
        "modalidade": "presencial",
        "termo_afirmativo": "transcidadania",
        "url_candidatura": "https://prefeitura.sp.gov.br/web/lgbti/w/menu/150965",
        "fonte": "Prefeitura de São Paulo · Transcidadania (https://prefeitura.sp.gov.br/web/lgbti/w/menu/150965)",
    },
    {
        "id_externo": "transempregos",
        "titulo": "TransEmpregos · banco de vagas para pessoas trans",
        "empresa": "TransEmpregos",
        "descricao": (
            "Maior banco de vagas e currículos voltado a pessoas trans no Brasil. "
            "As vagas e a candidatura ficam no site do projeto."
        ),
        "cidade": None,
        "uf": None,
        "modalidade": "nao_informada",
        "termo_afirmativo": "pessoas trans",
        "url_candidatura": "https://www.transempregos.org",
        "fonte": "TransEmpregos (https://www.transempregos.org)",
    },
]

# Retrato da resposta real de GET /cnes/estabelecimentos/2078015 (sem o e-mail, que é pessoal).
HC_FMUSP = {
    "codigo_cnes": 2078015,
    "nome": "HC DA FMUSP HOSPITAL DAS CLINICAS SAO PAULO",
    "razao_social": "FUNDACAO FACULDADE DE MEDICINA MEC MPAS",
    "codigo_municipio": 355030,
    "logradouro": "RUA DR OVIDIO PIRES DE CAMPOS",
    "numero": "225",
    "bairro": "CERQUEIRA CESAR",
    "cep": "05403010",
    "telefone": "(11)3087-5456",
    "latitude": -23.556591599413434,
    "longitude": -46.672325134277344,
    "tipo_unidade": 5,
    "atende_sus": True,
    "turno": "ATENDIMENTO CONTINUO DE 24 HORAS/DIA (PLANTAO:INCLUI SABADOS, DOMINGOS E FERIADOS)",
    "atualizado_no_cnes": date(2025, 9, 3),
    "fonte": "CNES/DATASUS (https://apidadosabertos.saude.gov.br/cnes/estabelecimentos/2078015)",
    "coletado_em": COLETA,
}


def upgrade() -> None:
    conexao = op.get_bind()
    meta = sa.MetaData()
    vagas = sa.Table("vagas", meta, autoload_with=conexao)
    municipios = sa.Table("municipios", meta, autoload_with=conexao)
    estabelecimentos = sa.Table("estabelecimentos_cnes", meta, autoload_with=conexao)
    habilitacoes = sa.Table("habilitacoes_cnes", meta, autoload_with=conexao)

    op.bulk_insert(vagas, [
        {
            **v,
            "origem": "curadoria",
            "cidade_busca": _normalizar(v["cidade"]),
            "afirmativa": True,
            "texto_busca": _normalizar(f"{v['titulo']} {v['empresa']} {v['descricao']}"),
            "publicada_em": None,
            "coletada_em": COLETA,
            "salario_min": None,
            "salario_max": None,
            "ativa": True,
            "exemplo": False,
        }
        for v in VAGAS
    ])
    op.bulk_insert(municipios, [{
        "codigo_ibge": 3550308, "nome": "São Paulo", "nome_busca": "sao paulo", "uf": "SP",
        "fonte": "IBGE Localidades (código oficial do município; a sincronização traz os demais de SP)",
        "coletado_em": COLETA,
    }])
    op.bulk_insert(estabelecimentos, [HC_FMUSP])
    op.bulk_insert(habilitacoes, [{
        "codigo_cnes": 2078015, "codigo": "30.02", "descricao": "Processo transexualizador",
        "fonte": FONTE_HABILITACAO, "verificado_em": VERIFICADO,
    }])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM habilitacoes_cnes WHERE codigo_cnes = 2078015 AND codigo = '30.02'"))
    op.execute(sa.text("DELETE FROM estabelecimentos_cnes WHERE codigo_cnes = 2078015"))
    op.execute(sa.text("DELETE FROM municipios WHERE codigo_ibge = 3550308"))
    op.execute(sa.text(
        "DELETE FROM vagas WHERE origem = 'curadoria' AND id_externo IN ('transcidadania', 'transempregos')"
    ))
