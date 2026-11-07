"""Contratos JSON que o app Expo consome. Ficam separados das entidades para
o domínio poder mudar sem quebrar o app (e vice-versa)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import Modalidade, NomeFonte, OrigemVaga, StatusSincronizacao

AVISO_CANDIDATURA = "A candidatura é feita no site de origem. O Aquenda não recebe nem guarda currículo."


class Saida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VagaResumo(Saida):
    id: int
    titulo: str
    empresa: str = Field(description="Nome da empresa como a fonte mandou.")
    empresa_id: int | None = Field(description="Empresa vinculada (GET /api/empresas/{id}). Nulo quando a fonte não diz.")
    cidade: str | None
    uf: str | None
    modalidade: Modalidade
    afirmativa: bool = Field(description="Verdadeiro quando o texto da vaga cita ação afirmativa, pessoas trans, travestis ou LGBT+.")
    termo_afirmativo: str | None = Field(description="Trecho do anúncio que tornou a vaga afirmativa.")
    origem: OrigemVaga
    publicada_em: datetime | None
    url_candidatura: str = Field(description="Link do site de origem, onde a pessoa se candidata.")
    exemplo: bool = Field(description="Item ilustrativo, sem fonte real. Só existe em dados de demonstração.")


class VagaDetalhe(VagaResumo):
    descricao: str
    fonte: str
    coletada_em: datetime = Field(description="Quando a API buscou esta vaga na fonte (UTC).")
    salario_min: float | None
    salario_max: float | None
    aviso: str = AVISO_CANDIDATURA


class PaginaVagas(BaseModel):
    itens: list[VagaResumo]
    total: int
    pagina: int
    tamanho: int
    total_paginas: int


class EmpresaEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=200, examples=["TransEmpregos"])
    site: str | None = Field(default=None, max_length=500, description="Link http(s).",
                             examples=["https://www.transempregos.org"])
    compromisso: str | None = Field(
        default=None, max_length=500, description="O que a empresa faz pela comunidade LGBTQIAPN+.",
        examples=["Maior banco de vagas e currículos de pessoas trans do Brasil."],
    )


class EmpresaSaida(BaseModel):
    id: int = Field(examples=[2])
    nome: str = Field(examples=["TransEmpregos"])
    site: str | None = Field(examples=["https://www.transempregos.org"])
    compromisso: str | None
    vagas_ativas: int = Field(description="Vagas no ar ligadas a esta empresa.", examples=[1])
    criada_em: datetime
    atualizada_em: datetime


class PaginaEmpresas(BaseModel):
    itens: list[EmpresaSaida]
    total: int
    pagina: int
    tamanho: int
    total_paginas: int


class EmpresaRemovida(BaseModel):
    id: int = Field(examples=[2])
    vagas_desvinculadas: int = Field(description="Vagas que continuam no ar, agora sem empresa vinculada.",
                                     examples=[1])


class MunicipioSaida(Saida):
    codigo_ibge: int = Field(examples=[3550308])
    codigo_cnes: int = Field(description="Código usado pelo DATASUS (IBGE sem o dígito verificador).", examples=[355030])
    nome: str = Field(examples=["São Paulo"])
    uf: str = Field(examples=["SP"])
    fonte: str
    coletado_em: datetime


class EstabelecimentoSaida(Saida):
    codigo_cnes: int = Field(examples=[2078015])
    nome: str
    razao_social: str
    endereco: str | None
    bairro: str | None
    cep: str | None
    telefone: str | None
    latitude: float | None
    longitude: float | None
    atende_sus: bool | None
    turno: str | None
    habilitacoes: list[str] = Field(examples=[["30.02"]])
    fonte: str
    coletado_em: datetime
    atualizado_no_cnes: date | None


class EstabelecimentosDoMunicipio(BaseModel):
    codigo_ibge: int
    municipio: MunicipioSaida | None = Field(description="Nulo se o IBGE ainda não foi sincronizado.")
    habilitacoes: list[str] | None = Field(description="Códigos usados no filtro. Nulo quando `todas=true`.")
    total: int
    itens: list[EstabelecimentoSaida]


class SincronizacaoSaida(Saida):
    status: StatusSincronizacao
    iniciada_em: datetime
    terminada_em: datetime | None
    itens: int
    mensagem: str | None


class EstadoFonteSaida(BaseModel):
    fonte: NomeFonte
    configurada: bool
    cache_valido: bool = Field(description="Se a última coleta boa ainda está dentro do prazo de cache.")
    ultima: SincronizacaoSaida | None
    ultima_com_sucesso: SincronizacaoSaida | None


class ResultadoSincronizacaoSaida(BaseModel):
    fonte: NomeFonte
    status: StatusSincronizacao
    itens: int
    mensagem: str | None


class Saude(BaseModel):
    status: str = Field(examples=["ok"])
    banco: str = Field(examples=["ok"])


class Problema(BaseModel):
    """Erro no formato ProblemDetails (RFC 7807), igual à API C#."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
