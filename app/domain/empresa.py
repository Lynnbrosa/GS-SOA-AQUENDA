"""Empresa que anuncia vagas. Cada vaga aponta para a sua empresa (chave estrangeira em vagas.empresa_id).

A sincronização cria a empresa na primeira vez que ela aparece numa fonte; a curadoria do grupo
completa o cadastro (site e compromisso com a comunidade) pelas rotas de operador.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.comum import DomainError, garantir_utc, limpar_html, normalizar
from app.domain.vaga import validar_url_publica

SEM_EMPRESA = "Empresa não informada"
TAMANHO_MAX_NOME = 200
TAMANHO_MAX_COMPROMISSO = 500


def _nome_valido(nome: str | None) -> str:
    nome = limpar_html(nome)
    if len(nome) < 2:
        raise DomainError("A empresa precisa de um nome com pelo menos 2 letras.")
    if len(nome) > TAMANHO_MAX_NOME:
        raise DomainError(f"O nome da empresa vai até {TAMANHO_MAX_NOME} caracteres.")
    if normalizar(nome) == normalizar(SEM_EMPRESA):
        raise DomainError(f'"{SEM_EMPRESA}" não é uma empresa: é o que a vaga mostra quando a fonte não diz.')
    return nome


def _site_valido(site: str | None) -> str | None:
    site = (site or "").strip()
    if not site:
        return None
    try:
        return validar_url_publica(site)
    except DomainError as erro:
        raise DomainError("O site da empresa precisa ser um link http(s).") from erro


def _compromisso_valido(compromisso: str | None) -> str | None:
    texto = limpar_html(compromisso)
    if len(texto) > TAMANHO_MAX_COMPROMISSO:
        raise DomainError(f"O compromisso vai até {TAMANHO_MAX_COMPROMISSO} caracteres.")
    return texto or None


@dataclass
class Empresa:
    nome: str
    criada_em: datetime
    atualizada_em: datetime
    site: str | None = None
    compromisso: str | None = None
    id: int | None = field(default=None)

    @classmethod
    def criar(cls, *, nome: str, agora: datetime, site: str | None = None, compromisso: str | None = None) -> "Empresa":
        """Única porta de entrada: nome limpo e de verdade, site só http(s)."""
        momento = garantir_utc(agora)
        return cls(
            nome=_nome_valido(nome), site=_site_valido(site), compromisso=_compromisso_valido(compromisso),
            criada_em=momento, atualizada_em=momento,
        )

    @staticmethod
    def e_empresa(nome: str | None) -> bool:
        """A vaga diz quem é a empresa? "Empresa não informada" e vazio não contam."""
        limpo = normalizar(limpar_html(nome))
        return len(limpo) >= 2 and limpo != normalizar(SEM_EMPRESA)

    @property
    def nome_busca(self) -> str:
        """Identidade natural: "Itaú", "ITAU" e "itaú " são a mesma empresa."""
        return normalizar(self.nome)

    def atualizar(self, *, nome: str, site: str | None, compromisso: str | None, agora: datetime) -> None:
        self.nome = _nome_valido(nome)
        self.site = _site_valido(site)
        self.compromisso = _compromisso_valido(compromisso)
        self.atualizada_em = garantir_utc(agora)
