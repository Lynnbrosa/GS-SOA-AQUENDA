"""Empresas: evolução do esquema com chave estrangeira.

Até a 0004, a empresa era só um texto dentro da vaga. Agora ela vira uma tabela própria,
e cada vaga aponta para a sua empresa:

- cria a tabela `empresas` (nome único sem acento e sem diferença de maiúscula, site e
  compromisso com a comunidade);
- acrescenta `vagas.empresa_id`, chave estrangeira para `empresas.id` com ON DELETE SET NULL
  (apagar a empresa não apaga a vaga) e um índice;
- carrega as empresas que já estão nas vagas e liga cada vaga à sua. "Empresa não informada"
  não vira empresa: a vaga fica com empresa_id nulo.

O texto `vagas.empresa` continua: é o nome como a fonte mandou, e o app já usa.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07
"""
import re
import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEM_EMPRESA = "empresa nao informada"


def _normalizar(texto: str | None) -> str:
    """Cópia congelada de app.domain.comum.normalizar: a migração não pode mudar se o código mudar."""
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def upgrade() -> None:
    op.create_table(
        "empresas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("nome_busca", sa.String(length=200), nullable=False),
        sa.Column("site", sa.String(length=500), nullable=True),
        sa.Column("compromisso", sa.String(length=500), nullable=True),
        sa.Column("criada_em", sa.DateTime(), nullable=False),
        sa.Column("atualizada_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("empresas", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_empresas_nome_busca"), ["nome_busca"], unique=True)

    # SQLite não tem ALTER TABLE ... ADD CONSTRAINT: o batch recria a tabela com a chave nova.
    with op.batch_alter_table("vagas", schema=None) as batch_op:
        batch_op.add_column(sa.Column("empresa_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_vagas_empresa_id"), ["empresa_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_vagas_empresa_id_empresas", "empresas", ["empresa_id"], ["id"], ondelete="SET NULL",
        )

    # dados: uma empresa por nome (sem acento, sem maiúscula), na grafia em que apareceu primeiro
    conexao = op.get_bind()
    agora = datetime.now(UTC).replace(tzinfo=None)
    vagas = conexao.execute(sa.text("SELECT id, empresa FROM vagas ORDER BY id")).all()
    primeiro_nome: dict[str, str] = {}
    for _, empresa in vagas:
        chave = _normalizar(empresa)
        if len(chave) >= 2 and chave != SEM_EMPRESA:
            primeiro_nome.setdefault(chave, empresa.strip())
    empresas = sa.table(
        "empresas", sa.column("nome", sa.String), sa.column("nome_busca", sa.String),
        sa.column("criada_em", sa.DateTime), sa.column("atualizada_em", sa.DateTime),
    )
    if primeiro_nome:
        op.bulk_insert(empresas, [
            {"nome": nome, "nome_busca": chave, "criada_em": agora, "atualizada_em": agora}
            for chave, nome in primeiro_nome.items()
        ])
    ids = dict(conexao.execute(sa.text("SELECT nome_busca, id FROM empresas")).all())
    for vaga_id, empresa in vagas:
        empresa_id = ids.get(_normalizar(empresa))
        if empresa_id is not None:
            conexao.execute(sa.text("UPDATE vagas SET empresa_id = :e WHERE id = :v"), {"e": empresa_id, "v": vaga_id})


def downgrade() -> None:
    with op.batch_alter_table("vagas", schema=None) as batch_op:
        batch_op.drop_constraint("fk_vagas_empresa_id_empresas", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_vagas_empresa_id"))
        batch_op.drop_column("empresa_id")
    with op.batch_alter_table("empresas", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_empresas_nome_busca"))
    op.drop_table("empresas")
