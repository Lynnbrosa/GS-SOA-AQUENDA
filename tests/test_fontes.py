"""Adaptadores HTTP contra respostas gravadas: o que cada fonte manda vira entidade do domínio."""

from datetime import UTC, datetime

import httpx
import pytest

from app.application.portas import FonteIndisponivel
from app.domain.enums import Modalidade
from app.infrastructure.fontes.governo import CnesFonte, IbgeFonte
from app.infrastructure.fontes.http import criar_cliente
from app.infrastructure.fontes.vagas import AdzunaFonte, GupyFonte
from tests.conftest import ADZUNA, CNES, GUPY, IBGE, carregar

AGORA = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def cliente(settings):
    with criar_cliente(settings) as c:
        yield c


# ------------------------------------------------------------- Adzuna

def test_adzuna_converte_e_descarta_item_malformado(mock_http, cliente, settings):
    rota = mock_http.get(url__startswith=f"{ADZUNA}/1").respond(200, json=carregar("adzuna_busca.json"))

    vagas = AdzunaFonte(cliente, settings).buscar(AGORA)

    assert [v.id_externo for v in vagas] == ["4811000001", "4811000002"]
    afirmativa, motorista = vagas
    assert afirmativa.afirmativa and afirmativa.modalidade == Modalidade.HIBRIDO
    assert (afirmativa.cidade, afirmativa.uf) == ("São Paulo", "SP")
    assert afirmativa.titulo.startswith("Analista de Dados Jr. - Vaga afirmativa")
    assert (afirmativa.salario_min, afirmativa.salario_max) == (3800, 4500)
    assert afirmativa.url_candidatura.startswith("https://www.adzuna.com.br/")
    assert not motorista.afirmativa, "'transporte' não pode virar 'trans'"

    params = rota.calls.last.request.url.params
    assert params["app_id"] == "id-de-teste"
    assert params["where"] == "São Paulo"


def test_adzuna_chave_recusada_vira_fonte_indisponivel(mock_http, cliente, settings):
    mock_http.get(url__startswith=ADZUNA).respond(401, json=carregar("adzuna_401.json"))
    with pytest.raises(FonteIndisponivel, match="401"):
        AdzunaFonte(cliente, settings).buscar(AGORA)


def test_adzuna_fora_do_ar_e_formato_estranho(mock_http, cliente, settings):
    mock_http.get(url__startswith=ADZUNA).mock(side_effect=httpx.ConnectTimeout("lento"))
    with pytest.raises(FonteIndisponivel, match="a tempo"):
        AdzunaFonte(cliente, settings).buscar(AGORA)

    mock_http.get(url__startswith=ADZUNA).respond(200, text="<html>manutenção</html>")
    with pytest.raises(FonteIndisponivel, match="JSON"):
        AdzunaFonte(cliente, settings).buscar(AGORA)


def test_adzuna_sem_chave_nao_esta_configurada(cliente, settings):
    sem_chave = settings.model_copy(update={"adzuna_app_key": ""})
    assert not AdzunaFonte(cliente, sem_chave).configurada()


# ------------------------------------------------------------- Gupy

def test_gupy_junta_os_termos_sem_duplicar(fontes_ok, cliente, settings):
    vagas = GupyFonte(cliente, settings).buscar(AGORA)

    por_id = {v.id_externo: v for v in vagas}
    assert sorted(por_id) == ["9100001", "9100002", "9100004"], "9100003 tem link javascript: e sai"
    assert por_id["9100001"].modalidade == Modalidade.HIBRIDO
    assert por_id["9100001"].descricao == "Esta é uma vaga afirmativa para pessoas LGBTQIAPN+."
    assert por_id["9100002"].modalidade == Modalidade.REMOTO
    assert por_id["9100002"].cidade is None and por_id["9100002"].uf is None
    assert por_id["9100004"].modalidade == Modalidade.PRESENCIAL
    assert not por_id["9100004"].afirmativa
    assert fontes_ok["gupy_afirmativa"].call_count == 1


def test_gupy_mudou_de_formato(mock_http, cliente, settings):
    mock_http.get(GUPY).respond(200, json={"jobs": []})
    with pytest.raises(FonteIndisponivel, match="formato"):
        GupyFonte(cliente, settings).buscar(AGORA)


def test_gupy_endpoint_sumiu(mock_http, cliente, settings):
    mock_http.get(GUPY).respond(404, text="<html>404</html>")
    with pytest.raises(FonteIndisponivel, match="404"):
        GupyFonte(cliente, settings).buscar(AGORA)


# ------------------------------------------------------------- CNES

def test_cnes_converte_resposta_gravada_sem_email(mock_http, cliente, settings):
    mock_http.get(f"{CNES}/estabelecimentos/2078015").respond(200, json=carregar("cnes_estabelecimento_2078015.json"))

    e = CnesFonte(cliente, settings).obter(2078015, AGORA)

    assert e.nome == "HC DA FMUSP HOSPITAL DAS CLINICAS SAO PAULO"
    assert e.codigo_municipio == 355030
    assert e.endereco == "RUA DR OVIDIO PIRES DE CAMPOS, 225"
    assert e.cep == "05403010" and e.atende_sus is True
    assert e.atualizado_no_cnes.isoformat() == "2025-09-03"
    assert e.coletado_em == AGORA
    assert "apidadosabertos.saude.gov.br" in e.fonte
    assert not any("@" in str(v) for v in vars(e).values()), "e-mail não pode ser guardado"


def test_cnes_codigo_inexistente_devolve_none(mock_http, cliente, settings):
    mock_http.get(f"{CNES}/estabelecimentos/1").respond(404, json=carregar("cnes_estabelecimento_inexistente.json"))
    assert CnesFonte(cliente, settings).obter(1, AGORA) is None


def test_cnes_erro_do_servidor(mock_http, cliente, settings):
    mock_http.get(f"{CNES}/estabelecimentos/2078015").respond(503)
    with pytest.raises(FonteIndisponivel, match="503"):
        CnesFonte(cliente, settings).obter(2078015, AGORA)


# ------------------------------------------------------------- IBGE

def test_ibge_converte_e_acha_uf_mesmo_sem_microrregiao(mock_http, cliente, settings):
    mock_http.get(f"{IBGE}/estados/SP/municipios").respond(200, json=carregar("ibge_municipios_sp.json"))

    municipios = IbgeFonte(cliente, settings).municipios("SP", AGORA)

    assert [m.codigo_ibge for m in municipios] == [3550308, 3518800, 3509502, 3513801]
    assert all(m.uf == "SP" for m in municipios)
    assert municipios[2].nome == "Campinas"


def test_ibge_conexao_recusada(mock_http, cliente, settings):
    mock_http.get(f"{IBGE}/estados/SP/municipios").mock(side_effect=httpx.ConnectError("reset"))
    with pytest.raises(FonteIndisponivel, match="fora do ar"):
        IbgeFonte(cliente, settings).municipios("SP", AGORA)
