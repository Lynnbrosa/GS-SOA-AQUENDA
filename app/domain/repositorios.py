"""Contratos de persistência. O domínio diz o que precisa; a infraestrutura implementa."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.enums import Modalidade, NomeFonte, OrigemVaga
from app.domain.localidades import EstabelecimentoCnes, Municipio
from app.domain.sincronizacao import Sincronizacao
from app.domain.vaga import Vaga


@dataclass(frozen=True)
class FiltroVagas:
    texto: str | None = None
    cidade: str | None = None
    uf: str | None = None
    afirmativa: bool | None = None
    modalidade: Modalidade | None = None
    origem: OrigemVaga | None = None
    pagina: int = 1
    tamanho: int = 20


class VagaRepository(Protocol):
    def buscar(self, filtro: FiltroVagas) -> tuple[list[Vaga], int]: ...
    def obter(self, vaga_id: int) -> Vaga | None: ...
    def obter_por_chave(self, origem: OrigemVaga, id_externo: str) -> Vaga | None: ...
    def salvar(self, vaga: Vaga) -> Vaga: ...
    def desativar_nao_vistas(self, origem: OrigemVaga, vistas_desde: datetime) -> int: ...


class MunicipioRepository(Protocol):
    def listar(self, uf: str | None, nome: str | None) -> list[Municipio]: ...
    def obter(self, codigo_ibge: int) -> Municipio | None: ...
    def salvar(self, municipio: Municipio) -> None: ...


class EstabelecimentoRepository(Protocol):
    def listar_por_municipio(self, codigo_municipio: int, habilitacao: str | None) -> list[EstabelecimentoCnes]: ...
    def obter(self, codigo_cnes: int) -> EstabelecimentoCnes | None: ...
    def salvar(self, estabelecimento: EstabelecimentoCnes) -> None: ...
    def codigos_habilitados(self, habilitacao: str) -> list[int]: ...


class SincronizacaoRepository(Protocol):
    def registrar(self, sincronizacao: Sincronizacao) -> Sincronizacao: ...
    def ultima(self, fonte: NomeFonte) -> Sincronizacao | None: ...
    def ultima_com_sucesso(self, fonte: NomeFonte) -> Sincronizacao | None: ...


class UnidadeDeTrabalho(Protocol):
    vagas: VagaRepository
    municipios: MunicipioRepository
    estabelecimentos: EstabelecimentoRepository
    sincronizacoes: SincronizacaoRepository

    def confirmar(self) -> None: ...
    def desfazer(self) -> None: ...
