"""Portas para o mundo de fora. A aplicação só conhece estes contratos;
os adaptadores HTTP (Adzuna, Gupy, CNES, IBGE) ficam na infraestrutura."""

from datetime import datetime
from typing import Protocol

from app.domain.enums import NomeFonte, OrigemVaga
from app.domain.localidades import EstabelecimentoCnes, Municipio
from app.domain.vaga import Vaga


class FonteIndisponivel(Exception):
    """A fonte caiu, demorou, recusou a chave ou mudou o formato.
    Quem chama mantém o que já está em cache."""


class FonteDeVagas(Protocol):
    nome: NomeFonte
    origem: OrigemVaga

    def configurada(self) -> bool: ...

    def buscar(self, agora: datetime) -> list[Vaga]: ...


class FonteCnes(Protocol):
    def obter(self, codigo_cnes: int, agora: datetime) -> EstabelecimentoCnes | None: ...


class FonteIbge(Protocol):
    def municipios(self, uf: str, agora: datetime) -> list[Municipio]: ...


class Relogio(Protocol):
    def __call__(self) -> datetime: ...
