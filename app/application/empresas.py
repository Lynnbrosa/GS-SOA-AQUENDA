"""Casos de uso das empresas: o CRUD que a curadoria do grupo usa para completar o cadastro.

Ler é livre (o app mostra a empresa da vaga); criar, editar e apagar exigem a chave de operador,
como a sincronização. Um commit por caso de uso.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.application.consultas import TAMANHO_MAXIMO_PAGINA, Pagina
from app.application.erros import ParametroInvalido, RecursoNaoEncontrado
from app.domain.comum import DomainError
from app.domain.empresa import Empresa
from app.domain.repositorios import FiltroEmpresas, UnidadeDeTrabalho


@dataclass(frozen=True)
class DadosEmpresa:
    nome: str
    site: str | None = None
    compromisso: str | None = None


@dataclass(frozen=True)
class EmpresaComVagas:
    empresa: Empresa
    vagas_ativas: int


class EmpresaService:
    def __init__(self, uow: UnidadeDeTrabalho, relogio: Callable[[], datetime]) -> None:
        self._uow = uow
        self._agora = relogio

    def buscar(self, filtro: FiltroEmpresas) -> Pagina[EmpresaComVagas]:
        if filtro.pagina < 1:
            raise ParametroInvalido("pagina começa em 1.")
        if not 1 <= filtro.tamanho <= TAMANHO_MAXIMO_PAGINA:
            raise ParametroInvalido(f"tamanho vai de 1 a {TAMANHO_MAXIMO_PAGINA}.")
        empresas, total = self._uow.empresas.buscar(filtro)
        itens = [EmpresaComVagas(e, self._uow.empresas.contar_vagas_ativas(e.id)) for e in empresas]
        return Pagina(itens=itens, total=total, pagina=filtro.pagina, tamanho=filtro.tamanho)

    def obter(self, empresa_id: int) -> EmpresaComVagas:
        empresa = self._existente(empresa_id)
        return EmpresaComVagas(empresa, self._uow.empresas.contar_vagas_ativas(empresa_id))

    def criar(self, dados: DadosEmpresa) -> EmpresaComVagas:
        empresa = Empresa.criar(nome=dados.nome, site=dados.site, compromisso=dados.compromisso, agora=self._agora())
        self._nome_livre(empresa.nome)
        self._uow.empresas.salvar(empresa)
        self._uow.confirmar()
        return EmpresaComVagas(empresa, 0)

    def atualizar(self, empresa_id: int, dados: DadosEmpresa) -> EmpresaComVagas:
        empresa = self._existente(empresa_id)
        empresa.atualizar(nome=dados.nome, site=dados.site, compromisso=dados.compromisso, agora=self._agora())
        self._nome_livre(empresa.nome, ignorar_id=empresa_id)
        self._uow.empresas.salvar(empresa)
        self._uow.confirmar()
        return EmpresaComVagas(empresa, self._uow.empresas.contar_vagas_ativas(empresa_id))

    def remover(self, empresa_id: int) -> int:
        """Apaga a empresa. As vagas dela continuam no ar, sem empresa vinculada; devolve quantas eram."""
        self._existente(empresa_id)
        desvinculadas = self._uow.empresas.remover(empresa_id)
        self._uow.confirmar()
        return desvinculadas

    def _existente(self, empresa_id: int) -> Empresa:
        empresa = self._uow.empresas.obter(empresa_id)
        if empresa is None:
            raise RecursoNaoEncontrado(f"Empresa {empresa_id} não existe.")
        return empresa

    def _nome_livre(self, nome: str, ignorar_id: int | None = None) -> None:
        outra = self._uow.empresas.obter_por_nome(nome)
        if outra is not None and outra.id != ignorar_id:
            raise DomainError(f'Já existe a empresa "{outra.nome}" (id {outra.id}). Edite essa em vez de criar outra.')
