"""Repositórios SQLAlchemy: traduzem entre as entidades do domínio e as tabelas."""

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.domain.comum import normalizar
from app.domain.empresa import Empresa
from app.domain.enums import Modalidade, NomeFonte, OrigemVaga, StatusSincronizacao
from app.domain.localidades import EstabelecimentoCnes, Municipio
from app.domain.repositorios import FiltroEmpresas, FiltroVagas
from app.domain.sincronizacao import Sincronizacao
from app.domain.vaga import Vaga
from app.infrastructure.db.modelos import (
    EmpresaModel, EstabelecimentoModel, HabilitacaoModel, MunicipioModel, SincronizacaoModel, VagaModel,
)


def _escapar_like(texto: str) -> str:
    """Quem busca "100%" não pode virar um curinga."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------- vagas

def _vaga_para_dominio(m: VagaModel) -> Vaga:
    return Vaga(
        id=m.id, origem=OrigemVaga(m.origem), id_externo=m.id_externo, titulo=m.titulo, empresa=m.empresa,
        descricao=m.descricao, cidade=m.cidade, uf=m.uf, modalidade=Modalidade(m.modalidade),
        termo_afirmativo=m.termo_afirmativo, url_candidatura=m.url_candidatura, fonte=m.fonte,
        publicada_em=m.publicada_em, coletada_em=m.coletada_em, salario_min=m.salario_min,
        salario_max=m.salario_max, ativa=m.ativa, exemplo=m.exemplo, empresa_id=m.empresa_id,
    )


def _vaga_para_modelo(v: Vaga, m: VagaModel) -> VagaModel:
    m.origem = v.origem.value
    m.id_externo = v.id_externo
    m.titulo = v.titulo
    m.empresa = v.empresa
    m.descricao = v.descricao
    m.cidade = v.cidade
    m.cidade_busca = v.cidade_busca
    m.uf = v.uf
    m.modalidade = v.modalidade.value
    m.afirmativa = v.afirmativa
    m.termo_afirmativo = v.termo_afirmativo
    m.texto_busca = v.texto_busca
    m.url_candidatura = v.url_candidatura
    m.fonte = v.fonte
    m.publicada_em = v.publicada_em
    m.coletada_em = v.coletada_em
    m.salario_min = v.salario_min
    m.salario_max = v.salario_max
    m.ativa = v.ativa
    m.exemplo = v.exemplo
    m.empresa_id = v.empresa_id
    return m


class SqlVagaRepository:
    def __init__(self, sessao: Session) -> None:
        self._s = sessao

    def buscar(self, filtro: FiltroVagas) -> tuple[list[Vaga], int]:
        consulta = select(VagaModel).where(VagaModel.ativa.is_(True))
        if filtro.texto:
            for palavra in normalizar(filtro.texto).split():
                consulta = consulta.where(
                    VagaModel.texto_busca.like(f"%{_escapar_like(palavra)}%", escape="\\")
                )
        if filtro.cidade:
            consulta = consulta.where(
                VagaModel.cidade_busca.like(f"%{_escapar_like(normalizar(filtro.cidade))}%", escape="\\")
            )
        if filtro.uf:
            consulta = consulta.where(VagaModel.uf == filtro.uf.upper())
        if filtro.afirmativa is not None:
            consulta = consulta.where(VagaModel.afirmativa.is_(filtro.afirmativa))
        if filtro.modalidade:
            consulta = consulta.where(VagaModel.modalidade == filtro.modalidade.value)
        if filtro.origem:
            consulta = consulta.where(VagaModel.origem == filtro.origem.value)
        if filtro.empresa_id is not None:
            consulta = consulta.where(VagaModel.empresa_id == filtro.empresa_id)

        total = self._s.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        # Curadoria (Transcidadania, TransEmpregos) primeiro; depois as mais novas.
        consulta = (
            consulta.order_by(
                (VagaModel.origem != OrigemVaga.CURADORIA.value),
                func.coalesce(VagaModel.publicada_em, VagaModel.coletada_em).desc(),
                VagaModel.id,
            )
            .offset((filtro.pagina - 1) * filtro.tamanho)
            .limit(filtro.tamanho)
        )
        return [_vaga_para_dominio(m) for m in self._s.scalars(consulta)], total

    def obter(self, vaga_id: int) -> Vaga | None:
        m = self._s.get(VagaModel, vaga_id)
        return _vaga_para_dominio(m) if m else None

    def obter_por_chave(self, origem: OrigemVaga, id_externo: str) -> Vaga | None:
        m = self._s.scalar(
            select(VagaModel).where(VagaModel.origem == origem.value, VagaModel.id_externo == id_externo)
        )
        return _vaga_para_dominio(m) if m else None

    def salvar(self, vaga: Vaga) -> Vaga:
        m = self._s.get(VagaModel, vaga.id) if vaga.id else VagaModel()
        _vaga_para_modelo(vaga, m)
        self._s.add(m)
        self._s.flush()
        vaga.id = m.id
        return vaga

    def desativar_nao_vistas(self, origem: OrigemVaga, vistas_desde: datetime) -> int:
        resultado = self._s.execute(
            update(VagaModel)
            .where(VagaModel.origem == origem.value, VagaModel.ativa.is_(True), VagaModel.coletada_em < vistas_desde)
            .values(ativa=False)
        )
        return resultado.rowcount or 0


# ---------------------------------------------------------------- empresas

def _empresa_para_dominio(m: EmpresaModel) -> Empresa:
    return Empresa(id=m.id, nome=m.nome, site=m.site, compromisso=m.compromisso,
                   criada_em=m.criada_em, atualizada_em=m.atualizada_em)


class SqlEmpresaRepository:
    def __init__(self, sessao: Session) -> None:
        self._s = sessao

    def buscar(self, filtro: FiltroEmpresas) -> tuple[list[Empresa], int]:
        consulta = select(EmpresaModel)
        if filtro.nome:
            consulta = consulta.where(
                EmpresaModel.nome_busca.like(f"%{_escapar_like(normalizar(filtro.nome))}%", escape="\\")
            )
        total = self._s.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        consulta = (consulta.order_by(EmpresaModel.nome_busca, EmpresaModel.id)
                    .offset((filtro.pagina - 1) * filtro.tamanho).limit(filtro.tamanho))
        return [_empresa_para_dominio(m) for m in self._s.scalars(consulta)], total

    def obter(self, empresa_id: int) -> Empresa | None:
        m = self._s.get(EmpresaModel, empresa_id)
        return _empresa_para_dominio(m) if m else None

    def obter_por_nome(self, nome: str) -> Empresa | None:
        m = self._s.scalar(select(EmpresaModel).where(EmpresaModel.nome_busca == normalizar(nome)))
        return _empresa_para_dominio(m) if m else None

    def salvar(self, empresa: Empresa) -> Empresa:
        m = self._s.get(EmpresaModel, empresa.id) if empresa.id else EmpresaModel()
        m.nome = empresa.nome
        m.nome_busca = empresa.nome_busca
        m.site = empresa.site
        m.compromisso = empresa.compromisso
        m.criada_em = empresa.criada_em
        m.atualizada_em = empresa.atualizada_em
        self._s.add(m)
        self._s.flush()
        empresa.id = m.id
        return empresa

    def remover(self, empresa_id: int) -> int:
        vinculadas = self._s.scalar(select(func.count()).where(VagaModel.empresa_id == empresa_id)) or 0
        # O banco faz o resto: a chave estrangeira tem ON DELETE SET NULL.
        self._s.execute(delete(EmpresaModel).where(EmpresaModel.id == empresa_id))
        self._s.expire_all()
        return vinculadas

    def contar_vagas_ativas(self, empresa_id: int) -> int:
        return self._s.scalar(
            select(func.count()).where(VagaModel.empresa_id == empresa_id, VagaModel.ativa.is_(True))
        ) or 0


# ---------------------------------------------------------------- municípios

class SqlMunicipioRepository:
    def __init__(self, sessao: Session) -> None:
        self._s = sessao

    def listar(self, uf: str | None, nome: str | None) -> list[Municipio]:
        consulta = select(MunicipioModel)
        if uf:
            consulta = consulta.where(MunicipioModel.uf == uf.upper())
        if nome:
            consulta = consulta.where(
                MunicipioModel.nome_busca.like(f"%{_escapar_like(normalizar(nome))}%", escape="\\")
            )
        consulta = consulta.order_by(MunicipioModel.nome_busca)
        return [self._dominio(m) for m in self._s.scalars(consulta)]

    def obter(self, codigo_ibge: int) -> Municipio | None:
        m = self._s.get(MunicipioModel, codigo_ibge)
        return self._dominio(m) if m else None

    def salvar(self, municipio: Municipio) -> None:
        m = self._s.get(MunicipioModel, municipio.codigo_ibge) or MunicipioModel(codigo_ibge=municipio.codigo_ibge)
        m.nome = municipio.nome
        m.nome_busca = normalizar(municipio.nome)
        m.uf = municipio.uf
        m.fonte = municipio.fonte
        m.coletado_em = municipio.coletado_em
        self._s.add(m)

    @staticmethod
    def _dominio(m: MunicipioModel) -> Municipio:
        return Municipio(codigo_ibge=m.codigo_ibge, nome=m.nome, uf=m.uf, fonte=m.fonte, coletado_em=m.coletado_em)


# ---------------------------------------------------------------- CNES

_CAMPOS_ESTABELECIMENTO = (
    "nome", "razao_social", "codigo_municipio", "logradouro", "numero", "bairro", "cep", "telefone",
    "latitude", "longitude", "tipo_unidade", "atende_sus", "turno", "atualizado_no_cnes", "fonte", "coletado_em",
)


class SqlEstabelecimentoRepository:
    def __init__(self, sessao: Session) -> None:
        self._s = sessao

    def listar_por_municipio(self, codigo_municipio: int, habilitacoes: list[str] | None) -> list[EstabelecimentoCnes]:
        consulta = select(EstabelecimentoModel).where(EstabelecimentoModel.codigo_municipio == codigo_municipio)
        if habilitacoes is not None:
            consulta = consulta.where(
                EstabelecimentoModel.codigo_cnes.in_(
                    select(HabilitacaoModel.codigo_cnes).where(HabilitacaoModel.codigo.in_(habilitacoes))
                )
            )
        consulta = consulta.order_by(EstabelecimentoModel.nome)
        return [self._dominio(m) for m in self._s.scalars(consulta)]

    def obter(self, codigo_cnes: int) -> EstabelecimentoCnes | None:
        m = self._s.get(EstabelecimentoModel, codigo_cnes)
        return self._dominio(m) if m else None

    def salvar(self, e: EstabelecimentoCnes) -> None:
        m = self._s.get(EstabelecimentoModel, e.codigo_cnes) or EstabelecimentoModel(codigo_cnes=e.codigo_cnes)
        for campo in _CAMPOS_ESTABELECIMENTO:
            setattr(m, campo, getattr(e, campo))
        self._s.add(m)

    def codigos_habilitados(self, habilitacoes: list[str]) -> list[int]:
        return list(
            self._s.scalars(
                select(HabilitacaoModel.codigo_cnes)
                .where(HabilitacaoModel.codigo.in_(habilitacoes))
                .distinct()
                .order_by(HabilitacaoModel.codigo_cnes)
            )
        )

    def _dominio(self, m: EstabelecimentoModel) -> EstabelecimentoCnes:
        dados = {campo: getattr(m, campo) for campo in _CAMPOS_ESTABELECIMENTO}
        return EstabelecimentoCnes(
            codigo_cnes=m.codigo_cnes,
            habilitacoes=sorted({h.codigo for h in m.habilitacoes}),
            **dados,
        )


# ---------------------------------------------------------------- sincronizações

class SqlSincronizacaoRepository:
    def __init__(self, sessao: Session) -> None:
        self._s = sessao

    def registrar(self, s: Sincronizacao) -> Sincronizacao:
        m = SincronizacaoModel(
            fonte=s.fonte.value, status=s.status.value, iniciada_em=s.iniciada_em, terminada_em=s.terminada_em,
            itens=s.itens, mensagem=(s.mensagem or None) and s.mensagem[:500],
        )
        self._s.add(m)
        self._s.flush()
        s.id = m.id
        return s

    def ultima(self, fonte: NomeFonte) -> Sincronizacao | None:
        return self._primeira(select(SincronizacaoModel).where(SincronizacaoModel.fonte == fonte.value))

    def ultima_com_sucesso(self, fonte: NomeFonte) -> Sincronizacao | None:
        return self._primeira(
            select(SincronizacaoModel).where(
                SincronizacaoModel.fonte == fonte.value,
                SincronizacaoModel.status == StatusSincronizacao.SUCESSO.value,
            )
        )

    def _primeira(self, consulta) -> Sincronizacao | None:
        m = self._s.scalar(consulta.order_by(SincronizacaoModel.iniciada_em.desc(), SincronizacaoModel.id.desc()))
        if m is None:
            return None
        return Sincronizacao(
            id=m.id, fonte=NomeFonte(m.fonte), status=StatusSincronizacao(m.status), iniciada_em=m.iniciada_em,
            terminada_em=m.terminada_em, itens=m.itens, mensagem=m.mensagem,
        )


# ---------------------------------------------------------------- unidade de trabalho

class SqlUnidadeDeTrabalho:
    """Um commit por caso de uso: ou a sincronização inteira entra, ou nada entra."""

    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao
        self.vagas = SqlVagaRepository(sessao)
        self.empresas = SqlEmpresaRepository(sessao)
        self.municipios = SqlMunicipioRepository(sessao)
        self.estabelecimentos = SqlEstabelecimentoRepository(sessao)
        self.sincronizacoes = SqlSincronizacaoRepository(sessao)

    def confirmar(self) -> None:
        self.sessao.commit()

    def desfazer(self) -> None:
        self.sessao.rollback()

