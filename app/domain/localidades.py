"""Município (IBGE) e estabelecimento de saúde (CNES)."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from app.domain.comum import DomainError, garantir_utc

# Código IBGE de UF: os dois primeiros dígitos do código do município.
UFS_IBGE = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA",
    31: "MG", 32: "ES", 33: "RJ", 35: "SP",
    41: "PR", 42: "SC", 43: "RS",
    50: "MS", 51: "MT", 52: "GO", 53: "DF",
}

# Tabela de Habilitações do SCNES, Portaria GM/MS nº 2.803/2013 (arts. 8º e 9º).
HABILITACOES_PROCESSO_TRANSEXUALIZADOR = {
    "30.01": "Unidade de Atenção Especializada no Processo Transexualizador (código de 2008, segue válido)",
    "30.02": "Ambulatorial: acompanhamento clínico, pré e pós-operatório e hormonioterapia",
    "30.03": "Hospitalar: cirurgias e acompanhamento pré e pós-operatório",
}


def validar_codigo_ibge(codigo: int | str) -> int:
    """Código de município do IBGE: 7 dígitos, começando por uma UF que existe."""
    texto = str(codigo).strip()
    if not re.fullmatch(r"\d{7}", texto):
        raise DomainError("Código IBGE de município tem 7 dígitos (ex.: 3550308 para São Paulo).")
    if int(texto[:2]) not in UFS_IBGE:
        raise DomainError(f"Código IBGE {texto} não começa com uma UF válida.")
    return int(texto)


def codigo_municipio_cnes(codigo_ibge: int) -> int:
    """O DATASUS usa o código IBGE sem o dígito verificador: 3550308 vira 355030."""
    return validar_codigo_ibge(codigo_ibge) // 10


def validar_codigo_cnes(codigo: int | str) -> int:
    texto = str(codigo).strip()
    if not re.fullmatch(r"\d{1,7}", texto) or int(texto) == 0:
        raise DomainError("Código CNES tem até 7 dígitos.")
    return int(texto)


@dataclass
class Municipio:
    codigo_ibge: int
    nome: str
    uf: str
    fonte: str
    coletado_em: datetime

    @classmethod
    def criar(cls, *, codigo_ibge: int | str, nome: str, uf: str, fonte: str, coletado_em: datetime) -> "Municipio":
        codigo = validar_codigo_ibge(codigo_ibge)
        uf = (uf or "").strip().upper()
        if UFS_IBGE[codigo // 100000] != uf:
            raise DomainError(f"Código {codigo} não é da UF {uf}.")
        if not (nome or "").strip():
            raise DomainError("Município precisa de nome.")
        return cls(codigo_ibge=codigo, nome=nome.strip(), uf=uf, fonte=fonte, coletado_em=garantir_utc(coletado_em))

    @property
    def codigo_cnes(self) -> int:
        return self.codigo_ibge // 10


@dataclass
class EstabelecimentoCnes:
    """Estabelecimento de saúde do CNES. Guardamos só dado institucional:
    o e-mail que o CNES publica costuma ser de uma pessoa e não entra aqui."""

    codigo_cnes: int
    nome: str
    razao_social: str
    codigo_municipio: int  # 6 dígitos, como no DATASUS
    fonte: str
    coletado_em: datetime
    habilitacoes: list[str] = field(default_factory=list)
    logradouro: str | None = None
    numero: str | None = None
    bairro: str | None = None
    cep: str | None = None
    telefone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    tipo_unidade: int | None = None
    atende_sus: bool | None = None
    turno: str | None = None
    atualizado_no_cnes: date | None = None

    @classmethod
    def criar(cls, *, codigo_cnes: int | str, nome: str | None, razao_social: str | None,
              codigo_municipio: int, fonte: str, coletado_em: datetime, **extras) -> "EstabelecimentoCnes":
        codigo = validar_codigo_cnes(codigo_cnes)
        nome_final = (nome or razao_social or "").strip()
        if not nome_final:
            raise DomainError("Estabelecimento sem nome no CNES.")
        if not re.fullmatch(r"\d{6}", str(codigo_municipio)):
            raise DomainError("Município do CNES tem 6 dígitos.")
        lat, lon = extras.get("latitude"), extras.get("longitude")
        if lat is not None and not -90 <= lat <= 90 or lon is not None and not -180 <= lon <= 180:
            extras["latitude"] = extras["longitude"] = None
        cep = re.sub(r"\D", "", extras.get("cep") or "") or None
        extras["cep"] = cep if cep and len(cep) == 8 else None
        return cls(
            codigo_cnes=codigo,
            nome=nome_final,
            razao_social=(razao_social or nome_final).strip(),
            codigo_municipio=int(codigo_municipio),
            fonte=fonte,
            coletado_em=garantir_utc(coletado_em),
            **extras,
        )

    @property
    def endereco(self) -> str | None:
        """Rua e número; o bairro vai em campo próprio."""
        return ", ".join(p for p in (self.logradouro, self.numero) if p) or None

    def tem_habilitacao(self, codigo: str) -> bool:
        return codigo in self.habilitacoes

    def atualizar_com(self, novo: "EstabelecimentoCnes") -> None:
        """Dados do CNES mudam; a lista de habilitações vem da curadoria e é preservada."""
        habilitacoes = sorted(set(self.habilitacoes) | set(novo.habilitacoes))
        for nome, valor in vars(novo).items():
            setattr(self, nome, valor)
        self.habilitacoes = habilitacoes
