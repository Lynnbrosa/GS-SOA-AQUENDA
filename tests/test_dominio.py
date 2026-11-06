"""Regras do domínio, sem banco e sem HTTP."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.afirmativa import eh_afirmativa, termo_afirmativo
from app.domain.comum import DomainError, limpar_html, normalizar
from app.domain.enums import Modalidade, NomeFonte, OrigemVaga, StatusSincronizacao
from app.domain.localidades import EstabelecimentoCnes, Municipio, codigo_municipio_cnes, validar_codigo_ibge
from app.domain.sincronizacao import Sincronizacao, cache_valido
from app.domain.vaga import Vaga, inferir_modalidade

AGORA = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def nova_vaga(**sobrescrever) -> Vaga:
    dados = dict(
        origem=OrigemVaga.GUPY, id_externo="1", titulo="Analista", empresa="Empresa Exemplo",
        url_candidatura="https://exemplo.gupy.io/job/1", fonte="Gupy", coletada_em=AGORA,
    )
    dados.update(sobrescrever)
    return Vaga.criar(**dados)


# ------------------------------------------------------------- vaga afirmativa

@pytest.mark.parametrize("texto, esperado", [
    ("Vaga afirmativa para pessoas trans", "pessoas trans"),
    ("VAGA AFIRMATIVA PARA PESSOAS TRANSGÊNERO", "pessoas transgenero"),
    ("Exclusiva para pessoas travestis e transexuais", "pessoas travestis"),
    ("Vaga Afirmativa Para Mulheres (Cis e Trans)", "cis e trans"),
    ("Banco de Talentos TIM - LGBTI+", "lgbti"),
    ("Buscamos pessoas LGBTQIAPN+", "lgbtqiapn"),
    ("Pessoa não binária, trans ou travesti", "pessoa nao binaria"),
])
def test_reconhece_vaga_afirmativa(texto, esperado):
    assert termo_afirmativo(texto) == esperado


@pytest.mark.parametrize("texto", [
    "Comprador Jr (Vaga Afirmativa - PCD)",
    "Processo seletivo afirmativo para pessoas negras",
    "Motorista de transporte escolar",
    "Analista de transações financeiras",
    "Transformação digital",
    "",
])
def test_nao_confunde_trans_com_outras_palavras(texto):
    assert not eh_afirmativa(texto)


def test_vaga_guarda_o_termo_que_a_tornou_afirmativa():
    vaga = nova_vaga(titulo="Dev Jr", descricao="<p>Vaga <b>afirmativa</b> para pessoas trans</p>")
    assert vaga.afirmativa
    assert vaga.termo_afirmativo == "pessoas trans"


def test_curadoria_pode_marcar_afirmativa_por_definicao():
    vaga = nova_vaga(titulo="Programa X", afirmativa_por_definicao="transcidadania")
    assert vaga.termo_afirmativo == "transcidadania"


# ------------------------------------------------------------- criação e validação

def test_limpa_html_do_titulo_e_da_descricao():
    vaga = nova_vaga(titulo="<strong>Analista</strong>&nbsp;Jr", descricao="<p>Linha 1</p><p>Linha 2</p>")
    assert vaga.titulo == "Analista Jr"
    assert vaga.descricao == "Linha 1 Linha 2"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://x.com", "", "https://", "/relativo"])
def test_recusa_link_de_candidatura_que_nao_e_http(url):
    with pytest.raises(DomainError):
        nova_vaga(url_candidatura=url)


def test_recusa_vaga_sem_titulo_ou_sem_fonte():
    with pytest.raises(DomainError):
        nova_vaga(titulo="  <br> ")
    with pytest.raises(DomainError):
        nova_vaga(fonte=" ")
    with pytest.raises(DomainError):
        nova_vaga(id_externo="")


def test_salario_invertido_e_corrigido_e_negativo_e_recusado():
    vaga = nova_vaga(salario_min=4500, salario_max=3800)
    assert (vaga.salario_min, vaga.salario_max) == (3800, 4500)
    with pytest.raises(DomainError):
        nova_vaga(salario_min=-1)


def test_empresa_vazia_vira_texto_explicito_e_uf_invalida_some():
    vaga = nova_vaga(empresa=None, uf="São Paulo")
    assert vaga.empresa == "Empresa não informada"
    assert vaga.uf is None


def test_data_sem_fuso_e_tratada_como_utc():
    vaga = nova_vaga(coletada_em=datetime(2026, 11, 10, 12, 0))
    assert vaga.coletada_em.tzinfo == UTC


@pytest.mark.parametrize("texto, esperado", [
    ("Modelo híbrido, 2x na semana", Modalidade.HIBRIDO),
    ("100% remoto", Modalidade.REMOTO),
    ("Home office", Modalidade.REMOTO),
    ("Trabalho presencial no centro", Modalidade.PRESENCIAL),
    ("Remoto com encontros: modelo hibrido", Modalidade.HIBRIDO),
    ("Sem informação", Modalidade.NAO_INFORMADA),
])
def test_infere_modalidade_pelo_texto(texto, esperado):
    assert inferir_modalidade(texto) == esperado


def test_atualizar_mantem_id_e_reativa():
    antiga = nova_vaga(titulo="Antigo")
    antiga.id, antiga.ativa = 7, False
    antiga.atualizar_com(nova_vaga(titulo="Novo título"))
    assert (antiga.id, antiga.titulo, antiga.ativa) == (7, "Novo título", True)


def test_texto_de_busca_ignora_acento_e_caixa():
    vaga = nova_vaga(titulo="Coordenação", empresa="AÇÃO Social")
    assert "coordenacao" in vaga.texto_busca
    assert "acao social" in vaga.texto_busca
    assert normalizar("  São   PAULO ") == "sao paulo"
    assert limpar_html(None) == ""


# ------------------------------------------------------------- IBGE e CNES

def test_codigo_ibge_valido_e_conversao_para_o_datasus():
    assert validar_codigo_ibge("3550308") == 3550308
    assert codigo_municipio_cnes(3550308) == 355030


@pytest.mark.parametrize("codigo", ["355030", "35503080", "9950308", "abc", ""])
def test_codigo_ibge_invalido(codigo):
    with pytest.raises(DomainError):
        validar_codigo_ibge(codigo)


def test_municipio_confere_a_uf_pelo_codigo():
    m = Municipio.criar(codigo_ibge=3550308, nome="São Paulo", uf="sp", fonte="IBGE", coletado_em=AGORA)
    assert (m.uf, m.codigo_cnes) == ("SP", 355030)
    with pytest.raises(DomainError):
        Municipio.criar(codigo_ibge=3550308, nome="São Paulo", uf="RJ", fonte="IBGE", coletado_em=AGORA)


def novo_estabelecimento(**extras) -> EstabelecimentoCnes:
    return EstabelecimentoCnes.criar(codigo_cnes=2078015, nome="HC", razao_social="Fundação",
                                     codigo_municipio=355030, fonte="CNES", coletado_em=AGORA, **extras)


def test_estabelecimento_limpa_cep_e_descarta_coordenada_impossivel():
    e = novo_estabelecimento(cep="05403-010", latitude=123.0, longitude=-46.6)
    assert e.cep == "05403010"
    assert (e.latitude, e.longitude) == (None, None)


def test_estabelecimento_sem_nome_ou_com_municipio_errado_e_recusado():
    with pytest.raises(DomainError):
        EstabelecimentoCnes.criar(codigo_cnes=1, nome=" ", razao_social=None, codigo_municipio=355030,
                                  fonte="CNES", coletado_em=AGORA)
    with pytest.raises(DomainError):
        EstabelecimentoCnes.criar(codigo_cnes=1, nome="X", razao_social=None, codigo_municipio=3550308,
                                  fonte="CNES", coletado_em=AGORA)


def test_atualizar_estabelecimento_preserva_habilitacoes_da_curadoria():
    existente = novo_estabelecimento()
    existente.habilitacoes = ["30.02"]
    existente.atualizar_com(novo_estabelecimento(telefone="(11) 0000-0000"))
    assert existente.telefone == "(11) 0000-0000"
    assert existente.tem_habilitacao("30.02")


# ------------------------------------------------------------- cache

def sinc(terminada_ha_minutos: int) -> Sincronizacao:
    return Sincronizacao(fonte=NomeFonte.GUPY, iniciada_em=AGORA, status=StatusSincronizacao.SUCESSO,
                         terminada_em=AGORA - timedelta(minutes=terminada_ha_minutos))


def test_cache_vale_dentro_do_prazo_e_expira_depois():
    assert cache_valido(sinc(59), AGORA, 60)
    assert not cache_valido(sinc(60), AGORA, 60)
    assert not cache_valido(None, AGORA, 60)
