"""Estrutura inicial: vagas, municípios, estabelecimentos CNES, habilitações e sincronizações.

Datas são gravadas em UTC sem fuso (o tipo UtcDateTime do código reanexa o fuso na leitura),
o que mantém a mesma migração válida em SQLite e PostgreSQL.

Revision ID: 0001
Revises:
Create Date: 2026-11-06
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('estabelecimentos_cnes',
    sa.Column('codigo_cnes', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.Column('razao_social', sa.String(length=200), nullable=False),
    sa.Column('codigo_municipio', sa.Integer(), nullable=False),
    sa.Column('logradouro', sa.String(length=200), nullable=True),
    sa.Column('numero', sa.String(length=20), nullable=True),
    sa.Column('bairro', sa.String(length=120), nullable=True),
    sa.Column('cep', sa.String(length=8), nullable=True),
    sa.Column('telefone', sa.String(length=40), nullable=True),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('tipo_unidade', sa.Integer(), nullable=True),
    sa.Column('atende_sus', sa.Boolean(), nullable=True),
    sa.Column('turno', sa.String(length=200), nullable=True),
    sa.Column('atualizado_no_cnes', sa.Date(), nullable=True),
    sa.Column('fonte', sa.String(length=300), nullable=False),
    sa.Column('coletado_em', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('codigo_cnes')
    )
    with op.batch_alter_table('estabelecimentos_cnes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_estabelecimentos_cnes_codigo_municipio'), ['codigo_municipio'], unique=False)

    op.create_table('habilitacoes_cnes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('codigo_cnes', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=10), nullable=False),
    sa.Column('descricao', sa.String(length=200), nullable=False),
    sa.Column('fonte', sa.String(length=300), nullable=False),
    sa.Column('verificado_em', sa.Date(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo_cnes', 'codigo', name='uq_habilitacao_cnes_codigo')
    )
    with op.batch_alter_table('habilitacoes_cnes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_habilitacoes_cnes_codigo'), ['codigo'], unique=False)
        batch_op.create_index(batch_op.f('ix_habilitacoes_cnes_codigo_cnes'), ['codigo_cnes'], unique=False)

    op.create_table('municipios',
    sa.Column('codigo_ibge', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('nome', sa.String(length=120), nullable=False),
    sa.Column('nome_busca', sa.String(length=120), nullable=False),
    sa.Column('uf', sa.String(length=2), nullable=False),
    sa.Column('fonte', sa.String(length=300), nullable=False),
    sa.Column('coletado_em', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('codigo_ibge')
    )
    with op.batch_alter_table('municipios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_municipios_nome_busca'), ['nome_busca'], unique=False)
        batch_op.create_index(batch_op.f('ix_municipios_uf'), ['uf'], unique=False)

    op.create_table('sincronizacoes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('fonte', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('iniciada_em', sa.DateTime(), nullable=False),
    sa.Column('terminada_em', sa.DateTime(), nullable=True),
    sa.Column('itens', sa.Integer(), nullable=False),
    sa.Column('mensagem', sa.String(length=500), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sincronizacoes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sincronizacoes_fonte'), ['fonte'], unique=False)

    op.create_table('vagas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('origem', sa.String(length=20), nullable=False),
    sa.Column('id_externo', sa.String(length=120), nullable=False),
    sa.Column('titulo', sa.String(length=200), nullable=False),
    sa.Column('empresa', sa.String(length=200), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=False),
    sa.Column('cidade', sa.String(length=120), nullable=True),
    sa.Column('cidade_busca', sa.String(length=120), nullable=False),
    sa.Column('uf', sa.String(length=2), nullable=True),
    sa.Column('modalidade', sa.String(length=20), nullable=False),
    sa.Column('afirmativa', sa.Boolean(), nullable=False),
    sa.Column('termo_afirmativo', sa.String(length=60), nullable=True),
    sa.Column('texto_busca', sa.Text(), nullable=False),
    sa.Column('url_candidatura', sa.String(length=500), nullable=False),
    sa.Column('fonte', sa.String(length=300), nullable=False),
    sa.Column('publicada_em', sa.DateTime(), nullable=True),
    sa.Column('coletada_em', sa.DateTime(), nullable=False),
    sa.Column('salario_min', sa.Float(), nullable=True),
    sa.Column('salario_max', sa.Float(), nullable=True),
    sa.Column('ativa', sa.Boolean(), nullable=False),
    sa.Column('exemplo', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('origem', 'id_externo', name='uq_vagas_origem_id_externo')
    )
    with op.batch_alter_table('vagas', schema=None) as batch_op:
        batch_op.create_index('ix_vagas_ativa_afirmativa', ['ativa', 'afirmativa'], unique=False)
        batch_op.create_index(batch_op.f('ix_vagas_cidade_busca'), ['cidade_busca'], unique=False)
        batch_op.create_index(batch_op.f('ix_vagas_modalidade'), ['modalidade'], unique=False)
        batch_op.create_index(batch_op.f('ix_vagas_uf'), ['uf'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('vagas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vagas_uf'))
        batch_op.drop_index(batch_op.f('ix_vagas_modalidade'))
        batch_op.drop_index(batch_op.f('ix_vagas_cidade_busca'))
        batch_op.drop_index('ix_vagas_ativa_afirmativa')

    op.drop_table('vagas')
    with op.batch_alter_table('sincronizacoes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sincronizacoes_fonte'))

    op.drop_table('sincronizacoes')
    with op.batch_alter_table('municipios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_municipios_uf'))
        batch_op.drop_index(batch_op.f('ix_municipios_nome_busca'))

    op.drop_table('municipios')
    with op.batch_alter_table('habilitacoes_cnes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_habilitacoes_cnes_codigo_cnes'))
        batch_op.drop_index(batch_op.f('ix_habilitacoes_cnes_codigo'))

    op.drop_table('habilitacoes_cnes')
    with op.batch_alter_table('estabelecimentos_cnes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_estabelecimentos_cnes_codigo_municipio'))

    op.drop_table('estabelecimentos_cnes')
