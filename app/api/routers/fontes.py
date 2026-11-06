from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import exigir_chave_operador, get_estado_fontes, get_sessao, get_sincronizacao
from app.api.erros import problema
from app.api.schemas import EstadoFonteSaida, Problema, ResultadoSincronizacaoSaida, Saude, SincronizacaoSaida
from app.application.sincronizacao import EstadoFontesService, SincronizacaoService
from app.domain.enums import NomeFonte

router = APIRouter(tags=["Fontes e saúde"])


@router.get("/api/fontes", response_model=list[EstadoFonteSaida], summary="Estado de cada fonte externa",
            description="De quando é o dado de cada fonte, se o cache ainda vale e qual foi o último erro.")
def listar_fontes(servico: Annotated[EstadoFontesService, Depends(get_estado_fontes)]) -> list[EstadoFonteSaida]:
    def _s(s):
        return SincronizacaoSaida.model_validate(s) if s else None

    return [
        EstadoFonteSaida(fonte=e.fonte, configurada=e.configurada, cache_valido=e.cache_valido,
                         ultima=_s(e.ultima), ultima_com_sucesso=_s(e.ultima_com_sucesso))
        for e in servico.listar()
    ]


@router.post(
    "/api/fontes/sincronizar",
    response_model=list[ResultadoSincronizacaoSaida],
    summary="Busca dados novos nas fontes",
    description=(
        "Sem `fonte`, sincroniza todas. Fonte com cache válido não é chamada, a não ser com `forcar=true`. "
        "Fonte fora do ar volta com status `falha` e o cache continua servindo. Exige `X-Chave-Operador` fora "
        "de desenvolvimento. Na VM, um timer do systemd chama `python -m app.cli sincronizar`."
    ),
    dependencies=[Depends(exigir_chave_operador)],
    responses={401: {"model": Problema}, 503: {"model": Problema}},
)
def sincronizar(
    servico: Annotated[SincronizacaoService, Depends(get_sincronizacao)],
    fonte: Annotated[NomeFonte | None, Query()] = None,
    forcar: Annotated[bool, Query()] = False,
) -> list[ResultadoSincronizacaoSaida]:
    resultados = [servico.sincronizar(fonte, forcar)] if fonte else servico.sincronizar_todas(forcar)
    return [ResultadoSincronizacaoSaida(fonte=r.fonte, status=r.status, itens=r.itens, mensagem=r.mensagem)
            for r in resultados]


@router.get("/health", response_model=Saude, summary="Saúde da API e do banco (para o monitoramento da VM)",
            responses={503: {"model": Problema}})
def saude(request: Request, sessao: Annotated[Session, Depends(get_sessao)]):
    try:
        sessao.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - qualquer falha do banco conta como "fora"
        return problema(request, 503, "Banco indisponível")
    return Saude(status="ok", banco="ok")
