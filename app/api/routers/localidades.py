from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_localidades
from app.api.schemas import EstabelecimentoSaida, EstabelecimentosDoMunicipio, MunicipioSaida, Problema
from app.application.consultas import LocalidadeService

router = APIRouter(tags=["Municípios e CNES"])

Servico = Annotated[LocalidadeService, Depends(get_localidades)]


@router.get("/api/municipios", response_model=list[MunicipioSaida], summary="Municípios (IBGE Localidades)",
            responses={400: {"model": Problema}})
def listar_municipios(
    servico: Servico,
    uf: Annotated[str | None, Query(min_length=2, max_length=2, examples=["SP"])] = None,
    nome: Annotated[str | None, Query(max_length=80, description="Parte do nome, sem diferenciar acento.", examples=["sao paulo"])] = None,
) -> list[MunicipioSaida]:
    return [MunicipioSaida.model_validate(m) for m in servico.listar_municipios(uf, nome)]


@router.get("/api/municipios/{codigo_ibge}", response_model=MunicipioSaida, summary="Um município pelo código IBGE",
            responses={400: {"model": Problema}, 404: {"model": Problema}})
def obter_municipio(servico: Servico, codigo_ibge: Annotated[int, Path(examples=[3550308])]) -> MunicipioSaida:
    return MunicipioSaida.model_validate(servico.obter_municipio(codigo_ibge))


@router.get(
    "/api/municipios/{codigo_ibge}/estabelecimentos",
    response_model=EstabelecimentosDoMunicipio,
    summary="Estabelecimentos CNES de um município",
    description=(
        "Por padrão traz quem tem habilitação no processo transexualizador do SUS: 30.01 (unidade, código de 2008), "
        "30.02 (ambulatorial: acompanhamento e hormonioterapia) ou 30.03 (hospitalar: cirurgias). "
        "Use `habilitacao` para um código só, ou `todas=true` para todos os estabelecimentos sincronizados."
    ),
    responses={400: {"model": Problema, "description": "Código IBGE inválido"}},
)
def estabelecimentos_do_municipio(
    servico: Servico,
    codigo_ibge: Annotated[int, Path(description="Código IBGE de 7 dígitos.", examples=[3550308])],
    habilitacao: Annotated[str | None, Query(max_length=5, examples=["30.02"])] = None,
    todas: Annotated[bool, Query(description="true = ignora habilitação.")] = False,
) -> EstabelecimentosDoMunicipio:
    municipio, filtro, itens = servico.estabelecimentos_do_municipio(codigo_ibge, habilitacao, todas)
    return EstabelecimentosDoMunicipio(
        codigo_ibge=codigo_ibge,
        municipio=MunicipioSaida.model_validate(municipio) if municipio else None,
        habilitacoes=filtro,
        total=len(itens),
        itens=[EstabelecimentoSaida.model_validate(e) for e in itens],
    )


@router.get("/api/cnes/estabelecimentos/{codigo_cnes}", response_model=EstabelecimentoSaida,
            summary="Um estabelecimento pelo código CNES", responses={400: {"model": Problema}, 404: {"model": Problema}})
def obter_estabelecimento(servico: Servico, codigo_cnes: Annotated[int, Path(examples=[2078015])]) -> EstabelecimentoSaida:
    return EstabelecimentoSaida.model_validate(servico.obter_estabelecimento(codigo_cnes))
