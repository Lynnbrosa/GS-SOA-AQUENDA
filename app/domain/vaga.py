"""Vaga de emprego agregada de uma fonte externa ou da curadoria."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

from app.domain.afirmativa import termo_afirmativo
from app.domain.comum import DomainError, garantir_utc, limpar_html, normalizar
from app.domain.enums import Modalidade, OrigemVaga

TAMANHO_MAX_DESCRICAO = 4000

_REMOTO = re.compile(r"\b(remot[oa]|home ?office|100% ?remot[oa]|teletrabalho)\b")
_HIBRIDO = re.compile(r"\bhibrid[oa]\b")
_PRESENCIAL = re.compile(r"\bpresencial\b")


def inferir_modalidade(*textos: str | None) -> Modalidade:
    """Para fontes sem campo de modalidade (Adzuna), lê o texto. Híbrido vence remoto."""
    alvo = " ".join(normalizar(t) for t in textos if t)
    if _HIBRIDO.search(alvo):
        return Modalidade.HIBRIDO
    if _REMOTO.search(alvo):
        return Modalidade.REMOTO
    if _PRESENCIAL.search(alvo):
        return Modalidade.PRESENCIAL
    return Modalidade.NAO_INFORMADA


def validar_url_publica(url: str) -> str:
    """A candidatura acontece no site de origem, então o link tem que ser http(s) válido."""
    url = (url or "").strip()
    partes = urlparse(url)
    if partes.scheme not in {"http", "https"} or not partes.netloc:
        raise DomainError("A vaga precisa de um link http(s) para o site de origem.")
    return url


@dataclass
class Vaga:
    origem: OrigemVaga
    id_externo: str
    titulo: str
    empresa: str
    url_candidatura: str
    fonte: str
    coletada_em: datetime
    descricao: str = ""
    cidade: str | None = None
    uf: str | None = None
    modalidade: Modalidade = Modalidade.NAO_INFORMADA
    termo_afirmativo: str | None = None
    publicada_em: datetime | None = None
    salario_min: float | None = None
    salario_max: float | None = None
    ativa: bool = True
    exemplo: bool = False
    empresa_id: int | None = None
    id: int | None = field(default=None)

    @classmethod
    def criar(
        cls,
        *,
        origem: OrigemVaga,
        id_externo: str,
        titulo: str,
        empresa: str | None,
        url_candidatura: str,
        fonte: str,
        coletada_em: datetime,
        descricao: str | None = None,
        cidade: str | None = None,
        uf: str | None = None,
        modalidade: Modalidade | None = None,
        publicada_em: datetime | None = None,
        salario_min: float | None = None,
        salario_max: float | None = None,
        afirmativa_por_definicao: str | None = None,
        exemplo: bool = False,
    ) -> "Vaga":
        """Única porta de entrada: limpa o texto, valida e decide se é afirmativa."""
        titulo = limpar_html(titulo)
        if not titulo:
            raise DomainError("A vaga precisa de um título.")
        if len(titulo) > 200:
            titulo = titulo[:200].rstrip()
        if not (id_externo or "").strip():
            raise DomainError("A vaga precisa do id da fonte para não duplicar.")
        if not (fonte or "").strip():
            raise DomainError("Toda vaga precisa dizer de onde veio.")

        descricao_limpa = limpar_html(descricao)[:TAMANHO_MAX_DESCRICAO]
        if salario_min is not None and salario_max is not None and salario_min > salario_max:
            salario_min, salario_max = salario_max, salario_min
        if (salario_min is not None and salario_min < 0) or (salario_max is not None and salario_max < 0):
            raise DomainError("Salário não pode ser negativo.")

        uf_limpa = (uf or "").strip().upper() or None
        if uf_limpa is not None and len(uf_limpa) != 2:
            uf_limpa = None

        termo = afirmativa_por_definicao or termo_afirmativo(titulo, descricao_limpa)

        return cls(
            origem=origem,
            id_externo=str(id_externo).strip(),
            titulo=titulo,
            empresa=limpar_html(empresa) or "Empresa não informada",
            url_candidatura=validar_url_publica(url_candidatura),
            fonte=fonte.strip(),
            coletada_em=garantir_utc(coletada_em),
            descricao=descricao_limpa,
            cidade=(cidade or "").strip() or None,
            uf=uf_limpa,
            modalidade=modalidade or inferir_modalidade(titulo, descricao_limpa),
            termo_afirmativo=termo,
            publicada_em=garantir_utc(publicada_em) if publicada_em else None,
            salario_min=salario_min,
            salario_max=salario_max,
            exemplo=exemplo,
        )

    @property
    def afirmativa(self) -> bool:
        return self.termo_afirmativo is not None

    @property
    def chave(self) -> tuple[OrigemVaga, str]:
        """Identidade natural: a mesma vaga da mesma fonte é atualizada, não duplicada."""
        return (self.origem, self.id_externo)

    @property
    def texto_busca(self) -> str:
        return normalizar(f"{self.titulo} {self.empresa} {self.descricao}")

    @property
    def cidade_busca(self) -> str:
        return normalizar(self.cidade)

    def atualizar_com(self, nova: "Vaga") -> None:
        """A fonte mandou de novo: troca o conteúdo, mantém o id e reativa."""
        for nome in (
            "titulo", "empresa", "descricao", "cidade", "uf", "modalidade", "termo_afirmativo",
            "url_candidatura", "fonte", "publicada_em", "salario_min", "salario_max", "coletada_em", "exemplo",
            "empresa_id",
        ):
            setattr(self, nome, getattr(nova, nome))
        self.ativa = True
