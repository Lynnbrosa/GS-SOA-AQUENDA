from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_vagas
from app.api.schemas import PaginaVagas, Problema, VagaDetalhe, VagaResumo
from app.application.consultas import TAMANHO_MAXIMO_PAGINA, VagaService
from app.domain.enums import Modalidade, OrigemVaga
from app.domain.repositorios import FiltroVagas

router = APIRouter(prefix="/api/vagas", tags=["Vagas"])

Servico = Annotated[VagaService, Depends(get_vagas)]


@router.get(
    "",
    response_model=PaginaVagas,
    summary="Lista e filtra vagas",
    description=(
        "Vagas agregadas da Adzuna, da Gupy e da curadoria (Transcidadania, TransEmpregos). "
        "Responde a partir do banco, então funciona mesmo com as fontes fora do ar. "
        "Curadoria aparece primeiro; depois, as mais recentes."
    ),
    responses={400: {"model": Problema, "description": "Filtro inválido"}},
)
def listar_vagas(
    servico: Servico,
    texto: Annotated[str | None, Query(
        max_length=100, description="Busca em título, empresa e descrição, sem diferenciar acento.", examples=["analista"],
    )] = None,
    cidade: Annotated[str | None, Query(max_length=80, examples=["São Paulo"])] = None,
    uf: Annotated[str | None, Query(min_length=2, max_length=2, examples=["SP"])] = None,
    afirmativa: Annotated[bool | None, Query(description="true = só vagas afirmativas.")] = None,
    modalidade: Annotated[Modalidade | None, Query()] = None,
    origem: Annotated[OrigemVaga | None, Query()] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=TAMANHO_MAXIMO_PAGINA)] = 20,
) -> PaginaVagas:
    resultado = servico.buscar(FiltroVagas(
        texto=texto, cidade=cidade, uf=uf, afirmativa=afirmativa, modalidade=modalidade,
        origem=origem, pagina=pagina, tamanho=tamanho,
    ))
    return PaginaVagas(
        itens=[VagaResumo.model_validate(v) for v in resultado.itens],
        total=resultado.total, pagina=resultado.pagina, tamanho=resultado.tamanho,
        total_paginas=resultado.total_paginas,
    )


@router.get(
    "/{vaga_id}",
    response_model=VagaDetalhe,
    summary="Detalhe de uma vaga",
    responses={404: {"model": Problema, "description": "Vaga inexistente ou fora do ar na fonte"}},
)
def obter_vaga(servico: Servico, vaga_id: Annotated[int, Path(ge=1)]) -> VagaDetalhe:
    return VagaDetalhe.model_validate(servico.obter(vaga_id))
