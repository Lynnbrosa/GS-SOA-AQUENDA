"""Tabelas do banco. Ficam na infraestrutura para o domínio não depender do SQLAlchemy."""

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Float, Index, Integer, String, Text, TypeDecorator, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class UtcDateTime(TypeDecorator):
    """Grava em UTC sem fuso (funciona igual em SQLite e PostgreSQL) e devolve com fuso UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Data sem fuso horário: use UTC.")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    pass


class VagaModel(Base):
    __tablename__ = "vagas"
    __table_args__ = (
        UniqueConstraint("origem", "id_externo", name="uq_vagas_origem_id_externo"),
        Index("ix_vagas_ativa_afirmativa", "ativa", "afirmativa"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origem: Mapped[str] = mapped_column(String(20))
    id_externo: Mapped[str] = mapped_column(String(120))
    titulo: Mapped[str] = mapped_column(String(200))
    empresa: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str] = mapped_column(Text, default="")
    cidade: Mapped[str | None] = mapped_column(String(120))
    cidade_busca: Mapped[str] = mapped_column(String(120), default="", index=True)
    uf: Mapped[str | None] = mapped_column(String(2), index=True)
    modalidade: Mapped[str] = mapped_column(String(20), index=True)
    afirmativa: Mapped[bool] = mapped_column(Boolean, default=False)
    termo_afirmativo: Mapped[str | None] = mapped_column(String(60))
    texto_busca: Mapped[str] = mapped_column(Text, default="")
    url_candidatura: Mapped[str] = mapped_column(String(500))
    fonte: Mapped[str] = mapped_column(String(300))
    publicada_em: Mapped[datetime | None] = mapped_column(UtcDateTime())
    coletada_em: Mapped[datetime] = mapped_column(UtcDateTime())
    salario_min: Mapped[float | None] = mapped_column(Float)
    salario_max: Mapped[float | None] = mapped_column(Float)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    exemplo: Mapped[bool] = mapped_column(Boolean, default=False)


class MunicipioModel(Base):
    __tablename__ = "municipios"

    codigo_ibge: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    nome: Mapped[str] = mapped_column(String(120))
    nome_busca: Mapped[str] = mapped_column(String(120), index=True)
    uf: Mapped[str] = mapped_column(String(2), index=True)
    fonte: Mapped[str] = mapped_column(String(300))
    coletado_em: Mapped[datetime] = mapped_column(UtcDateTime())


class EstabelecimentoModel(Base):
    __tablename__ = "estabelecimentos_cnes"

    codigo_cnes: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    nome: Mapped[str] = mapped_column(String(200))
    razao_social: Mapped[str] = mapped_column(String(200))
    codigo_municipio: Mapped[int] = mapped_column(Integer, index=True)
    logradouro: Mapped[str | None] = mapped_column(String(200))
    numero: Mapped[str | None] = mapped_column(String(20))
    bairro: Mapped[str | None] = mapped_column(String(120))
    cep: Mapped[str | None] = mapped_column(String(8))
    telefone: Mapped[str | None] = mapped_column(String(40))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    tipo_unidade: Mapped[int | None] = mapped_column(Integer)
    atende_sus: Mapped[bool | None] = mapped_column(Boolean)
    turno: Mapped[str | None] = mapped_column(String(200))
    atualizado_no_cnes: Mapped[date | None] = mapped_column(Date)
    fonte: Mapped[str] = mapped_column(String(300))
    coletado_em: Mapped[datetime] = mapped_column(UtcDateTime())

    habilitacoes: Mapped[list["HabilitacaoModel"]] = relationship(
        primaryjoin="EstabelecimentoModel.codigo_cnes == foreign(HabilitacaoModel.codigo_cnes)",
        lazy="selectin",
        viewonly=True,
    )


class HabilitacaoModel(Base):
    """Lista curada de quem tem qual habilitação. A API aberta do CNES não expõe
    habilitação, então a lista vem da portaria e o sync completa os dados do CNES."""

    __tablename__ = "habilitacoes_cnes"
    __table_args__ = (UniqueConstraint("codigo_cnes", "codigo", name="uq_habilitacao_cnes_codigo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_cnes: Mapped[int] = mapped_column(Integer, index=True)
    codigo: Mapped[str] = mapped_column(String(10), index=True)
    descricao: Mapped[str] = mapped_column(String(200))
    fonte: Mapped[str] = mapped_column(String(300))
    verificado_em: Mapped[date] = mapped_column(Date)


class SincronizacaoModel(Base):
    __tablename__ = "sincronizacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fonte: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20))
    iniciada_em: Mapped[datetime] = mapped_column(UtcDateTime())
    terminada_em: Mapped[datetime | None] = mapped_column(UtcDateTime())
    itens: Mapped[int] = mapped_column(Integer, default=0)
    mensagem: Mapped[str | None] = mapped_column(String(500))


__all__ = [
    "Base", "VagaModel", "MunicipioModel", "EstabelecimentoModel", "HabilitacaoModel", "SincronizacaoModel",
]
