"""Habilitações do processo transexualizador em SP a partir do arquivo oficial do CNES.

Fonte: arquivo de habilitações HBSP2609.dbc (competência 09/2026) do FTP do DATASUS
(ftp://ftp.datasus.gov.br/dissemin/publicos/CNES/200508_/Dados/HB/), lido com
scripts/habilitacoes_cnes.py em 06/11/2026. Substitui a lista da 0003, que vinha só da
Portaria 2.803/2013:

- o HC-FMUSP (2078015) tem 30.01, 30.02 e 30.03;
- o Instituto de Psiquiatria (2812703) não aparece mais habilitado e sai da lista
  (o estabelecimento continua na base, visível com todas=true);
- entram o CRT DST/Aids (capital) e quatro serviços no interior.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-06
"""
from collections.abc import Sequence
from datetime import UTC, date, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ARQUIVO = "CNES/DATASUS, arquivo oficial de habilitações HBSP2609.dbc (competência 09/2026)"
VERIFICADO = date(2026, 11, 6)
COLETA = datetime(2026, 11, 6, 4, 40, tzinfo=UTC).replace(tzinfo=None)

DESCRICOES = {
    "30.01": "Unidade de Atenção Especializada no Processo Transexualizador",
    "30.02": "Ambulatorial: acompanhamento clínico, pré e pós-operatório e hormonioterapia",
    "30.03": "Hospitalar: cirurgias e acompanhamento pré e pós-operatório",
}

# (CNES, código, portaria, data da portaria), exatamente como no arquivo HB.
HABILITACOES = [
    (2078015, "30.01", "PT GM 2.736", "10/12/2014"),
    (2078015, "30.02", "GM 3126", "28/12/2016"),
    (2078015, "30.03", "GM 3126", "28/12/2016"),
    (2077957, "30.02", "PT GM 3231", "29/12/2016"),
    (2079798, "30.02", "9352/GM/MS", "12/12/2025"),
    (2079798, "30.03", "9358/GM/MS", "12/12/2025"),
    (2097036, "30.02", "376/GM/MS", "28/03/2023"),
    (6487173, "30.02", "GM/MS 10120", "31/12/2025"),
    (6682774, "30.02", "9349/GM/MS", "12/12/2025"),
]

# Retratos de GET https://apidadosabertos.saude.gov.br/cnes/estabelecimentos/{cnes} (sem e-mail).
ESTABELECIMENTOS = [{'codigo_cnes': 2077957,
  'nome': 'CENTRO DE REFERENCIA E TREINAMENTO DST AIDS SAO PAULO',
  'razao_social': 'SECRETARIA DE ESTADO DA SAUDE DE SAO PAULO',
  'codigo_municipio': 355030,
  'logradouro': 'RUA SANTA CRUZ',
  'numero': '81',
  'bairro': 'VILA MARIANA',
  'cep': '04121000',
  'telefone': '(11) 5087-9911',
  'latitude': -23.5966194,
  'longitude': -46.635813324338585,
  'tipo_unidade': 7,
  'atende_sus': True,
  'turno': 'ATENDIMENTO NOS TURNOS DA MANHA, TARDE E NOITE',
  'atualizado_no_cnes': '2025-09-03'},
 {'codigo_cnes': 2079798,
  'nome': 'HOSPITAL DAS CLINICAS DA UNICAMP DE CAMPINAS',
  'razao_social': 'UNIVERSIDADE ESTADUAL DE CAMPINAS',
  'codigo_municipio': 350950,
  'logradouro': 'RUA VITAL BRASIL',
  'numero': '251',
  'bairro': 'BARAO GERALDO',
  'cep': '13024500',
  'telefone': '(19)37888008',
  'latitude': -22.905965260395842,
  'longitude': -47.06392765045166,
  'tipo_unidade': 5,
  'atende_sus': True,
  'turno': 'ATENDIMENTO CONTINUO DE 24 HORAS/DIA (PLANTAO:INCLUI SABADOS, DOMINGOS E FERIADOS)',
  'atualizado_no_cnes': '2025-09-03'},
 {'codigo_cnes': 2097036,
  'nome': 'AMBULATORIO DE DOENCAS CRONICAS TRANSMISSIVEIS',
  'razao_social': 'PREFEITURA MUNICIPAL DE SAO JOSE DO RIO PRETO',
  'codigo_municipio': 354980,
  'logradouro': 'RUA DO ROSARIO',
  'numero': '1903',
  'bairro': 'VILA ESPLANADA',
  'cep': '15030560',
  'telefone': '(17)32356667',
  'latitude': -20.796383554470754,
  'longitude': -49.37976433201907,
  'tipo_unidade': 36,
  'atende_sus': True,
  'turno': 'ATENDIMENTOS NOS TURNOS DA MANHA E A TARDE',
  'atualizado_no_cnes': '2025-09-03'},
 {'codigo_cnes': 6487173,
  'nome': 'CENTRO ESP DE DOENCAS INFECTOCONTAGIOSAS E IST AIDS CEI',
  'razao_social': 'PREFEITURA MUNICIPAL DE HORTOLANDIA',
  'codigo_municipio': 351907,
  'logradouro': 'AV THEREZA ANA CECON BREDA',
  'numero': '1115',
  'bairro': 'VILA SAO PEDRO',
  'cep': '13183091',
  'telefone': '(19) 3897.3653',
  'latitude': -22.858084470766784,
  'longitude': -47.22001075744629,
  'tipo_unidade': 36,
  'atende_sus': True,
  'turno': 'ATENDIMENTOS NOS TURNOS DA MANHA E A TARDE',
  'atualizado_no_cnes': '2025-09-03'},
 {'codigo_cnes': 6682774,
  'nome': 'CENTRO DE TESTAGEM E ACONSELHAMENTO CTA BAURU',
  'razao_social': 'PREFEITURA MUNICIPAL DE BAURU',
  'codigo_municipio': 350600,
  'logradouro': 'RUA 15 DE NOVEMBRO',
  'numero': '336',
  'bairro': 'CENTRO',
  'cep': '17015040',
  'telefone': '3234-2576',
  'latitude': -22.327648335210906,
  'longitude': -49.07517671585083,
  'tipo_unidade': 36,
  'atende_sus': True,
  'turno': 'ATENDIMENTOS NOS TURNOS DA MANHA E A TARDE',
  'atualizado_no_cnes': '2025-09-03'}]

# Municípios dos serviços novos (código IBGE de 7 dígitos; o DATASUS usa os 6 primeiros).
MUNICIPIOS = [
    (3509502, "Campinas"),
    (3549805, "São José do Rio Preto"),
    (3519071, "Hortolândia"),
    (3506003, "Bauru"),
]


def _normalizar(nome: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii").lower()


def upgrade() -> None:
    conexao = op.get_bind()
    meta = sa.MetaData()
    habilitacoes = sa.Table("habilitacoes_cnes", meta, autoload_with=conexao)
    estabelecimentos = sa.Table("estabelecimentos_cnes", meta, autoload_with=conexao)
    municipios = sa.Table("municipios", meta, autoload_with=conexao)

    conexao.execute(habilitacoes.delete())
    op.bulk_insert(habilitacoes, [
        {"codigo_cnes": cnes, "codigo": codigo, "descricao": DESCRICOES[codigo],
         "fonte": f"{ARQUIVO}: portaria {portaria} de {data}", "verificado_em": VERIFICADO}
        for cnes, codigo, portaria, data in HABILITACOES
    ])

    existentes = set(conexao.execute(sa.select(estabelecimentos.c.codigo_cnes)).scalars())
    op.bulk_insert(estabelecimentos, [
        {**e, "atualizado_no_cnes": date.fromisoformat(e["atualizado_no_cnes"]),
         "fonte": f"CNES/DATASUS (https://apidadosabertos.saude.gov.br/cnes/estabelecimentos/{e['codigo_cnes']})",
         "coletado_em": COLETA}
        for e in ESTABELECIMENTOS if e["codigo_cnes"] not in existentes
    ])

    ja_tem = set(conexao.execute(sa.select(municipios.c.codigo_ibge)).scalars())
    op.bulk_insert(municipios, [
        {"codigo_ibge": codigo, "nome": nome, "nome_busca": _normalizar(nome), "uf": "SP",
         "fonte": "IBGE Localidades (código oficial do município)", "coletado_em": COLETA}
        for codigo, nome in MUNICIPIOS if codigo not in ja_tem
    ])


def downgrade() -> None:
    novos = ", ".join(str(e["codigo_cnes"]) for e in ESTABELECIMENTOS)
    op.execute(sa.text("DELETE FROM habilitacoes_cnes"))
    op.execute(sa.text(f"DELETE FROM estabelecimentos_cnes WHERE codigo_cnes IN ({novos})"))
    # Municípios ficam: a sincronização do IBGE também os traz e não há como saber quem inseriu.
    fonte = (
        "Portaria GM/MS nº 2.803/2013, art. 9º, parágrafo único (alterado pela PRT 629/2014) "
        "(https://bvsms.saude.gov.br/bvs/saudelegis/gm/2013/prt2803_19_11_2013.html)"
    )
    for cnes in (2078015, 2812703):
        op.execute(sa.text(
            "INSERT INTO habilitacoes_cnes (codigo_cnes, codigo, descricao, fonte, verificado_em) "
            "VALUES (:cnes, '30.01', :descricao, :fonte, :verificado)"
        ).bindparams(cnes=cnes, descricao=DESCRICOES["30.01"], fonte=fonte, verificado=VERIFICADO))
