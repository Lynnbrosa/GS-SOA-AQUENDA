"""Casos de uso de leitura: o que o app Expo consome. Só leem o banco (o cache),
então continuam respondendo mesmo com todas as fontes externas fora do ar."""

import math
from dataclasses import dataclass
from typing import Generic, TypeVar

from app.application.erros import ParametroInvalido, RecursoNaoEncontrado
from app.domain.comum import DomainError
from app.domain.localidades import (
    HABILITACOES_PROCESSO_TRANSEXUALIZADOR, EstabelecimentoCnes, Municipio, validar_codigo_cnes, validar_codigo_ibge,
)
from app.domain.repositorios import FiltroVagas, UnidadeDeTrabalho
from app.domain.vaga import Vaga

T = TypeVar("T")

TAMANHO_MAXIMO_PAGINA = 50


@dataclass(frozen=True)
class Pagina(Generic[T]):
    itens: list[T]
    total: int
    pagina: int
    tamanho: int

    @property
    def total_paginas(self) -> int:
        return math.ceil(self.total / self.tamanho) if self.total else 0


class VagaService:
    def __init__(self, uow: UnidadeDeTrabalho) -> None:
        self._uow = uow

    def buscar(self, filtro: FiltroVagas) -> Pagina[Vaga]:
        if filtro.pagina < 1:
            raise ParametroInvalido("pagina começa em 1.")
        if not 1 <= filtro.tamanho <= TAMANHO_MAXIMO_PAGINA:
            raise ParametroInvalido(f"tamanho vai de 1 a {TAMANHO_MAXIMO_PAGINA}.")
        if filtro.uf is not None and len(filtro.uf.strip()) != 2:
            raise ParametroInvalido("uf é a sigla com 2 letras (ex.: SP).")
        itens, total = self._uow.vagas.buscar(filtro)
        return Pagina(itens=itens, total=total, pagina=filtro.pagina, tamanho=filtro.tamanho)

    def obter(self, vaga_id: int) -> Vaga:
        vaga = self._uow.vagas.obter(vaga_id)
        if vaga is None or not vaga.ativa:
            raise RecursoNaoEncontrado(f"Vaga {vaga_id} não existe ou já saiu do ar na fonte.")
        return vaga


class LocalidadeService:
    def __init__(self, uow: UnidadeDeTrabalho) -> None:
        self._uow = uow

    def listar_municipios(self, uf: str | None, nome: str | None) -> list[Municipio]:
        if uf is not None and len(uf.strip()) != 2:
            raise ParametroInvalido("uf é a sigla com 2 letras (ex.: SP).")
        return self._uow.municipios.listar(uf, nome)

    def obter_municipio(self, codigo_ibge: int) -> Municipio:
        codigo = self._codigo_ibge(codigo_ibge)
        municipio = self._uow.municipios.obter(codigo)
        if municipio is None:
            raise RecursoNaoEncontrado(f"Município {codigo} não está na base. Rode a sincronização do IBGE.")
        return municipio

    def estabelecimentos_do_municipio(
        self, codigo_ibge: int, habilitacao: str | None = None, todas: bool = False
    ) -> tuple[Municipio | None, list[str] | None, list[EstabelecimentoCnes]]:
        """Por padrão, quem tem qualquer habilitação do processo transexualizador (30.01, 30.02 ou 30.03)."""
        codigo = self._codigo_ibge(codigo_ibge)
        if todas:
            filtro = None
        elif habilitacao:
            if habilitacao not in HABILITACOES_PROCESSO_TRANSEXUALIZADOR:
                raise ParametroInvalido(
                    f"habilitacao deve ser uma de {', '.join(HABILITACOES_PROCESSO_TRANSEXUALIZADOR)}."
                )
            filtro = [habilitacao]
        else:
            filtro = list(HABILITACOES_PROCESSO_TRANSEXUALIZADOR)
        municipio = self._uow.municipios.obter(codigo)
        return municipio, filtro, self._uow.estabelecimentos.listar_por_municipio(codigo // 10, filtro)

    def obter_estabelecimento(self, codigo_cnes: int) -> EstabelecimentoCnes:
        try:
            codigo = validar_codigo_cnes(codigo_cnes)
        except DomainError as erro:
            raise ParametroInvalido(str(erro)) from erro
        estabelecimento = self._uow.estabelecimentos.obter(codigo)
        if estabelecimento is None:
            raise RecursoNaoEncontrado(f"Estabelecimento CNES {codigo} não está na base.")
        return estabelecimento

    @staticmethod
    def _codigo_ibge(codigo: int) -> int:
        try:
            return validar_codigo_ibge(codigo)
        except DomainError as erro:
            raise ParametroInvalido(str(erro)) from erro
