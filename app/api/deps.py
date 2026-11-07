"""Injeção de dependência: cada requisição ganha sua sessão e seus serviços."""

import hmac
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.application.consultas import LocalidadeService, VagaService
from app.application.empresas import EmpresaService
from app.application.sincronizacao import EstadoFontesService, PrazosCache, SincronizacaoService
from app.config import Settings
from app.infrastructure.repositorios.sql import SqlUnidadeDeTrabalho


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_sessao(request: Request) -> Iterator[Session]:
    sessao = request.app.state.fabrica()
    try:
        yield sessao
    finally:
        sessao.close()


def get_uow(sessao: Annotated[Session, Depends(get_sessao)]) -> SqlUnidadeDeTrabalho:
    return SqlUnidadeDeTrabalho(sessao)


Uow = Annotated[SqlUnidadeDeTrabalho, Depends(get_uow)]


def get_vagas(uow: Uow) -> VagaService:
    return VagaService(uow)


def get_empresas(request: Request, uow: Uow) -> EmpresaService:
    return EmpresaService(uow, request.app.state.relogio)


def get_localidades(uow: Uow) -> LocalidadeService:
    return LocalidadeService(uow)


def _prazos(s: Settings) -> PrazosCache:
    return PrazosCache(s.cache_minutos_vagas, s.cache_minutos_cnes, s.cache_minutos_ibge)


def get_sincronizacao(request: Request, uow: Uow) -> SincronizacaoService:
    estado = request.app.state
    return SincronizacaoService(
        uow,
        fontes_vagas=estado.fontes_vagas,
        fonte_cnes=estado.fonte_cnes,
        fonte_ibge=estado.fonte_ibge,
        relogio=estado.relogio,
        prazos=_prazos(estado.settings),
        uf_ibge=estado.settings.ibge_uf,
    )


def get_estado_fontes(
    request: Request, uow: Uow, sync: Annotated[SincronizacaoService, Depends(get_sincronizacao)]
) -> EstadoFontesService:
    return EstadoFontesService(uow, sync, request.app.state.relogio, _prazos(request.app.state.settings))


def exigir_chave_operador(
    settings: Annotated[Settings, Depends(get_settings)],
    x_chave_operador: Annotated[str | None, Header(description="Chave da equipe. Livre em desenvolvimento.")] = None,
) -> None:
    """Mesma regra da API C#: livre em desenvolvimento; fora dele, sem chave configurada = 503."""
    if settings.em_desenvolvimento and not settings.chave_operador:
        return
    if not settings.chave_operador:
        raise HTTPException(503, "Escrita desligada: configure CHAVE_OPERADOR no servidor.")
    if not x_chave_operador or not hmac.compare_digest(x_chave_operador.encode(), settings.chave_operador.encode()):
        raise HTTPException(401, "Chave de operador ausente ou inválida.")
