"""Casos de uso de escrita: buscar dados nas fontes externas e guardar no banco.

Regras que valem para toda fonte:
- Se a última coleta boa ainda está dentro do prazo de cache, a fonte não é chamada.
- Se a fonte falha, o que já está no banco fica intacto e a falha é registrada.
- Uma vaga que sumiu da fonte sai da listagem (fica inativa), mas só depois de uma
  coleta boa que trouxe alguma coisa: resposta vazia não apaga o cache.
- Toda vaga fica ligada à sua empresa (vagas.empresa_id). A empresa é criada na primeira vaga
  dela e reaproveitada depois, sem diferenciar acento nem maiúscula.
"""

import logging
from dataclasses import dataclass

from app.application.portas import FonteCnes, FonteDeVagas, FonteIbge, FonteIndisponivel, Relogio
from app.domain.comum import normalizar
from app.domain.empresa import Empresa
from app.domain.enums import NomeFonte, StatusSincronizacao
from app.domain.localidades import HABILITACOES_PROCESSO_TRANSEXUALIZADOR
from app.domain.repositorios import UnidadeDeTrabalho
from app.domain.sincronizacao import Sincronizacao, cache_valido

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrazosCache:
    vagas_minutos: int = 60
    cnes_minutos: int = 24 * 60
    ibge_minutos: int = 7 * 24 * 60

    def para(self, fonte: NomeFonte) -> int:
        if fonte == NomeFonte.CNES:
            return self.cnes_minutos
        if fonte == NomeFonte.IBGE:
            return self.ibge_minutos
        return self.vagas_minutos


@dataclass(frozen=True)
class Resultado:
    fonte: NomeFonte
    status: StatusSincronizacao
    itens: int
    mensagem: str | None = None


class SincronizacaoService:
    def __init__(
        self,
        uow: UnidadeDeTrabalho,
        fontes_vagas: list[FonteDeVagas],
        fonte_cnes: FonteCnes,
        fonte_ibge: FonteIbge,
        relogio: Relogio,
        prazos: PrazosCache | None = None,
        uf_ibge: str = "SP",
    ) -> None:
        self._uow = uow
        self._vagas = {f.nome: f for f in fontes_vagas}
        self._cnes = fonte_cnes
        self._ibge = fonte_ibge
        self._agora = relogio
        self._prazos = prazos or PrazosCache()
        self._uf = uf_ibge

    @property
    def fontes(self) -> list[NomeFonte]:
        return [*self._vagas.keys(), NomeFonte.CNES, NomeFonte.IBGE]

    def configurada(self, fonte: NomeFonte) -> bool:
        return self._vagas[fonte].configurada() if fonte in self._vagas else True

    def sincronizar_todas(self, forcar: bool = False) -> list[Resultado]:
        return [self.sincronizar(fonte, forcar) for fonte in self.fontes]

    def sincronizar(self, fonte: NomeFonte, forcar: bool = False) -> Resultado:
        if fonte not in self.fontes:
            raise ValueError(f"Fonte desconhecida: {fonte}")
        inicio = self._agora()

        if not self.configurada(fonte):
            return self._registrar(fonte, inicio, StatusSincronizacao.NAO_CONFIGURADA, 0,
                                   "Fonte sem chave configurada; a API segue com o que tem em cache.")

        ultima_ok = self._uow.sincronizacoes.ultima_com_sucesso(fonte)
        if not forcar and cache_valido(ultima_ok, inicio, self._prazos.para(fonte)):
            return Resultado(fonte, StatusSincronizacao.EM_CACHE, ultima_ok.itens,
                             f"Cache de {ultima_ok.terminada_em:%d/%m %H:%M} UTC ainda vale.")

        try:
            if fonte in self._vagas:
                itens, mensagem = self._sincronizar_vagas(self._vagas[fonte], inicio)
            elif fonte == NomeFonte.CNES:
                itens, mensagem = self._sincronizar_cnes(inicio)
            else:
                itens, mensagem = self._sincronizar_ibge(inicio)
        except FonteIndisponivel as erro:
            self._uow.desfazer()
            log.warning("Fonte %s indisponível: %s", fonte, erro)
            return self._registrar(fonte, inicio, StatusSincronizacao.FALHA, 0,
                                   f"{erro} A API segue respondendo com o cache.")
        except Exception:
            self._uow.desfazer()
            raise

        return self._registrar(fonte, inicio, StatusSincronizacao.SUCESSO, itens, mensagem)

    # ------------------------------------------------------------ por tipo de fonte

    def _empresa_id(self, nome: str, inicio, ja_vistas: dict[str, int]) -> int | None:
        if not Empresa.e_empresa(nome):
            return None
        chave = normalizar(nome)
        if chave not in ja_vistas:
            empresa = self._uow.empresas.obter_por_nome(nome)
            if empresa is None:
                empresa = self._uow.empresas.salvar(Empresa.criar(nome=nome, agora=inicio))
            ja_vistas[chave] = empresa.id
        return ja_vistas[chave]

    def _sincronizar_vagas(self, fonte: FonteDeVagas, inicio) -> tuple[int, str | None]:
        vagas = fonte.buscar(inicio)
        empresas: dict[str, int] = {}
        for nova in vagas:
            nova.empresa_id = self._empresa_id(nova.empresa, inicio, empresas)
            existente = self._uow.vagas.obter_por_chave(*nova.chave)
            if existente:
                existente.atualizar_com(nova)
                self._uow.vagas.salvar(existente)
            else:
                self._uow.vagas.salvar(nova)
        if not vagas:
            return 0, "A fonte respondeu sem vagas; o cache anterior foi mantido."
        saidas = self._uow.vagas.desativar_nao_vistas(fonte.origem, inicio)
        return len(vagas), (f"{saidas} vaga(s) saíram do ar na fonte." if saidas else None)

    def _sincronizar_cnes(self, inicio) -> tuple[int, str | None]:
        codigos = self._uow.estabelecimentos.codigos_habilitados(list(HABILITACOES_PROCESSO_TRANSEXUALIZADOR))
        atualizados, ausentes = 0, []
        for codigo in codigos:
            novo = self._cnes.obter(codigo, inicio)
            if novo is None:
                ausentes.append(str(codigo))
                continue
            existente = self._uow.estabelecimentos.obter(codigo)
            if existente:
                existente.atualizar_com(novo)
                novo = existente
            self._uow.estabelecimentos.salvar(novo)
            atualizados += 1
        mensagem = f"Não encontrados no CNES: {', '.join(ausentes)}." if ausentes else None
        return atualizados, mensagem

    def _sincronizar_ibge(self, inicio) -> tuple[int, str | None]:
        municipios = self._ibge.municipios(self._uf, inicio)
        if not municipios:
            raise FonteIndisponivel(f"IBGE respondeu sem municípios para {self._uf}.")
        for municipio in municipios:
            self._uow.municipios.salvar(municipio)
        return len(municipios), None

    def _registrar(self, fonte, inicio, status, itens, mensagem) -> Resultado:
        self._uow.sincronizacoes.registrar(
            Sincronizacao(fonte=fonte, iniciada_em=inicio, terminada_em=self._agora(), status=status,
                          itens=itens, mensagem=mensagem)
        )
        self._uow.confirmar()
        return Resultado(fonte, status, itens, mensagem)


@dataclass(frozen=True)
class EstadoFonte:
    fonte: NomeFonte
    configurada: bool
    cache_valido: bool
    ultima: Sincronizacao | None
    ultima_com_sucesso: Sincronizacao | None


class EstadoFontesService:
    """O que GET /api/fontes mostra: de quando é o dado que o app está vendo."""

    def __init__(self, uow: UnidadeDeTrabalho, sincronizacao: SincronizacaoService, relogio: Relogio,
                 prazos: PrazosCache | None = None) -> None:
        self._uow = uow
        self._sync = sincronizacao
        self._agora = relogio
        self._prazos = prazos or PrazosCache()

    def listar(self) -> list[EstadoFonte]:
        agora = self._agora()
        estados = []
        for fonte in self._sync.fontes:
            ok = self._uow.sincronizacoes.ultima_com_sucesso(fonte)
            estados.append(EstadoFonte(
                fonte=fonte,
                configurada=self._sync.configurada(fonte),
                cache_valido=cache_valido(ok, agora, self._prazos.para(fonte)),
                ultima=self._uow.sincronizacoes.ultima(fonte),
                ultima_com_sucesso=ok,
            ))
        return estados
