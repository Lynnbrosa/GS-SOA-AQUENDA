from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.deps import exigir_chave_operador, get_empresas
from app.api.schemas import EmpresaEntrada, EmpresaRemovida, EmpresaSaida, PaginaEmpresas, Problema
from app.application.consultas import TAMANHO_MAXIMO_PAGINA
from app.application.empresas import DadosEmpresa, EmpresaComVagas, EmpresaService
from app.domain.repositorios import FiltroEmpresas

router = APIRouter(prefix="/api/empresas", tags=["Empresas"])

Servico = Annotated[EmpresaService, Depends(get_empresas)]
IdEmpresa = Annotated[int, Path(ge=1, description="Id da empresa.", examples=[1])]

ERRO_OPERADOR = {
    401: {"model": Problema, "description": "Chave de operador ausente ou inválida"},
    503: {"model": Problema, "description": "Escrita desligada: o servidor não tem CHAVE_OPERADOR"},
}
ERRO_ENTRADA = {
    400: {"model": Problema, "description": "Campo com formato inválido (ex.: nome vazio)"},
    422: {"model": Problema, "description": "Regra de negócio: nome repetido, site que não é http(s)..."},
}
NAO_ENCONTRADA = {404: {"model": Problema, "description": "Empresa inexistente"}}


def _saida(item: EmpresaComVagas) -> EmpresaSaida:
    e = item.empresa
    return EmpresaSaida(id=e.id, nome=e.nome, site=e.site, compromisso=e.compromisso, vagas_ativas=item.vagas_ativas,
                        criada_em=e.criada_em, atualizada_em=e.atualizada_em)


def _dados(entrada: EmpresaEntrada) -> DadosEmpresa:
    return DadosEmpresa(nome=entrada.nome, site=entrada.site, compromisso=entrada.compromisso)


@router.get(
    "",
    response_model=PaginaEmpresas,
    summary="Lista as empresas",
    description="Em ordem alfabética, com quantas vagas ativas cada uma tem. `nome` busca sem diferenciar acento. "
                "Para ver as vagas de uma empresa: `GET /api/vagas?empresa_id={id}`.",
    responses={400: {"model": Problema, "description": "Filtro inválido"}},
)
def listar_empresas(
    servico: Servico,
    nome: Annotated[str | None, Query(max_length=100, examples=["transempregos"])] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=TAMANHO_MAXIMO_PAGINA)] = 20,
) -> PaginaEmpresas:
    resultado = servico.buscar(FiltroEmpresas(nome=nome, pagina=pagina, tamanho=tamanho))
    return PaginaEmpresas(itens=[_saida(i) for i in resultado.itens], total=resultado.total,
                          pagina=resultado.pagina, tamanho=resultado.tamanho, total_paginas=resultado.total_paginas)


@router.get("/{empresa_id}", response_model=EmpresaSaida, summary="Uma empresa", responses=NAO_ENCONTRADA)
def obter_empresa(servico: Servico, empresa_id: IdEmpresa) -> EmpresaSaida:
    return _saida(servico.obter(empresa_id))


@router.post(
    "",
    response_model=EmpresaSaida,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra uma empresa",
    description="Normalmente a sincronização cria a empresa sozinha na primeira vaga dela; a curadoria usa esta "
                "rota para empresas que ainda não anunciaram. O nome é único sem diferenciar acento nem maiúscula. "
                "Exige `X-Chave-Operador` fora de desenvolvimento.",
    dependencies=[Depends(exigir_chave_operador)],
    responses={**ERRO_ENTRADA, **ERRO_OPERADOR},
)
def criar_empresa(servico: Servico, entrada: EmpresaEntrada) -> EmpresaSaida:
    return _saida(servico.criar(_dados(entrada)))


@router.put(
    "/{empresa_id}",
    response_model=EmpresaSaida,
    summary="Atualiza uma empresa",
    description="Troca nome, site e compromisso (o que vier vazio fica vazio). As vagas continuam ligadas a ela. "
                "Exige `X-Chave-Operador` fora de desenvolvimento.",
    dependencies=[Depends(exigir_chave_operador)],
    responses={**NAO_ENCONTRADA, **ERRO_ENTRADA, **ERRO_OPERADOR},
)
def atualizar_empresa(servico: Servico, empresa_id: IdEmpresa, entrada: EmpresaEntrada) -> EmpresaSaida:
    return _saida(servico.atualizar(empresa_id, _dados(entrada)))


@router.delete(
    "/{empresa_id}",
    response_model=EmpresaRemovida,
    summary="Remove uma empresa",
    description="As vagas da empresa **não** são apagadas: continuam listadas, com `empresa_id` nulo (a chave "
                "estrangeira é ON DELETE SET NULL). A resposta diz quantas vagas ficaram sem empresa. "
                "Exige `X-Chave-Operador` fora de desenvolvimento.",
    dependencies=[Depends(exigir_chave_operador)],
    responses={**NAO_ENCONTRADA, **ERRO_OPERADOR},
)
def remover_empresa(servico: Servico, empresa_id: IdEmpresa) -> EmpresaRemovida:
    return EmpresaRemovida(id=empresa_id, vagas_desvinculadas=servico.remover(empresa_id))
