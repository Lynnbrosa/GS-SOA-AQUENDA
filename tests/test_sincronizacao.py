"""Sincronização ponta a ponta (HTTP gravado → banco real migrado → API), com foco no cache."""

import httpx

from tests.conftest import ADZUNA, CNES, IBGE, carregar


def sincronizar(client, **params):
    resposta = client.post("/api/fontes/sincronizar", params=params)
    assert resposta.status_code == 200, resposta.text
    return {r["fonte"]: r for r in resposta.json()}


def ids_externos(client, **params):
    return {v["url_candidatura"] for v in client.get("/api/vagas", params={"tamanho": 50, **params}).json()["itens"]}


def test_sincroniza_todas_as_fontes(client, fontes_ok):
    resultado = sincronizar(client)

    assert {f: r["status"] for f, r in resultado.items()} == {
        "adzuna": "sucesso", "gupy": "sucesso", "cnes": "sucesso", "ibge": "sucesso",
    }
    assert resultado["adzuna"]["itens"] == 2
    assert resultado["gupy"]["itens"] == 3
    assert resultado["ibge"]["itens"] == 4

    pagina = client.get("/api/vagas", params={"tamanho": 50}).json()
    assert pagina["total"] == 2 + 2 + 3  # curadoria + Adzuna + Gupy
    assert client.get("/api/municipios", params={"uf": "SP"}).json()[0]["nome"] == "Campinas"


def test_dentro_do_prazo_o_cache_responde_sem_chamar_a_fonte(client, fontes_ok, relogio):
    sincronizar(client, fonte="gupy")
    relogio.avancar(minutes=30)

    resultado = sincronizar(client, fonte="gupy")

    assert resultado["gupy"]["status"] == "em_cache"
    assert fontes_ok["gupy_afirmativa"].call_count == 1


def test_forcar_ignora_o_cache_e_prazo_vencido_busca_de_novo(client, fontes_ok, relogio):
    sincronizar(client, fonte="gupy")
    assert sincronizar(client, fonte="gupy", forcar="true")["gupy"]["status"] == "sucesso"
    relogio.avancar(minutes=61)
    assert sincronizar(client, fonte="gupy")["gupy"]["status"] == "sucesso"
    assert fontes_ok["gupy_afirmativa"].call_count == 3


def rotas_gupy(fontes_ok):
    return [rota for nome, rota in fontes_ok.items() if nome.startswith("gupy")]


def test_fonte_fora_do_ar_mantem_o_cache_e_registra_a_falha(client, fontes_ok, relogio):
    sincronizar(client, fonte="gupy")
    antes = ids_externos(client, origem="gupy")
    relogio.avancar(hours=2)
    for rota in rotas_gupy(fontes_ok):
        rota.mock(side_effect=httpx.ConnectError("caiu"))

    resultado = sincronizar(client, fonte="gupy")

    assert resultado["gupy"]["status"] == "falha"
    assert "cache" in resultado["gupy"]["mensagem"]
    assert ids_externos(client, origem="gupy") == antes, "nenhuma vaga pode sumir porque a fonte caiu"
    estado = {f["fonte"]: f for f in client.get("/api/fontes").json()}["gupy"]
    assert estado["ultima"]["status"] == "falha"
    assert estado["ultima_com_sucesso"]["itens"] == 3
    assert estado["cache_valido"] is False


def test_vaga_que_sumiu_da_fonte_sai_da_listagem(client, fontes_ok, relogio):
    sincronizar(client, fonte="gupy")
    vaga_id = next(v["id"] for v in client.get("/api/vagas", params={"origem": "gupy"}).json()["itens"]
                   if v["url_candidatura"].endswith("9100004"))
    relogio.avancar(hours=2)
    fontes_ok["gupy_trans"].respond(200, json={"data": [], "pagination": {}})

    resultado = sincronizar(client, fonte="gupy")

    assert "1 vaga(s) saíram do ar" in resultado["gupy"]["mensagem"]
    assert client.get(f"/api/vagas/{vaga_id}").status_code == 404
    assert len(ids_externos(client, origem="gupy")) == 2


def test_resposta_vazia_nao_apaga_o_cache(client, fontes_ok, relogio):
    sincronizar(client, fonte="gupy")
    relogio.avancar(hours=2)
    for rota in rotas_gupy(fontes_ok):
        rota.respond(200, json={"data": [], "pagination": {}})

    resultado = sincronizar(client, fonte="gupy")

    assert resultado["gupy"]["itens"] == 0
    assert "mantido" in resultado["gupy"]["mensagem"]
    assert len(ids_externos(client, origem="gupy")) == 3


def test_mesma_vaga_atualiza_em_vez_de_duplicar(client, fontes_ok, mock_http, relogio):
    sincronizar(client, fonte="adzuna")
    relogio.avancar(hours=2)
    dados = carregar("adzuna_busca.json")
    dados["results"][0]["title"] = "Analista de Dados Pleno - vaga afirmativa"
    mock_http.get(url__startswith=f"{ADZUNA}/1").respond(200, json=dados)

    sincronizar(client, fonte="adzuna")

    titulos = [v["titulo"] for v in client.get("/api/vagas", params={"origem": "adzuna"}).json()["itens"]]
    assert sorted(titulos) == ["Analista de Dados Pleno - vaga afirmativa", "Motorista de transporte escolar"]


def test_adzuna_sem_chave_fica_nao_configurada(settings, relogio, mock_http):
    from fastapi.testclient import TestClient

    from app.main import create_app

    sem_chave = settings.model_copy(update={"adzuna_app_id": "", "adzuna_app_key": ""})
    with TestClient(create_app(sem_chave, relogio)) as c:
        resultado = sincronizar(c, fonte="adzuna")
    assert resultado["adzuna"]["status"] == "nao_configurada"
    assert not mock_http.calls


def test_cnes_atualiza_o_retrato_e_avisa_codigo_inexistente(client, mock_http):
    dados = carregar("cnes_estabelecimento_2078015.json")
    dados["numero_telefone_estabelecimento"] = "(11) 2661-0000"
    mock_http.get(f"{CNES}/estabelecimentos/2078015").respond(200, json=dados)
    mock_http.get(f"{CNES}/estabelecimentos/2812703").respond(404, json=carregar("cnes_estabelecimento_inexistente.json"))

    resultado = sincronizar(client, fonte="cnes")
    assert (resultado["cnes"]["status"], resultado["cnes"]["itens"]) == ("sucesso", 1)
    assert resultado["cnes"]["mensagem"] == "Não encontrados no CNES: 2812703."
    assert client.get("/api/cnes/estabelecimentos/2812703").status_code == 200, "o retrato anterior continua"

    hc = client.get("/api/cnes/estabelecimentos/2078015").json()
    assert hc["telefone"] == "(11) 2661-0000"
    assert hc["habilitacoes"] == ["30.01"], "habilitação vem da curadoria e sobrevive ao sync"
    assert hc["coletado_em"] == "2026-11-10T12:00:00Z"


def test_ibge_fora_do_ar_nao_derruba_a_consulta_de_estabelecimentos(client, mock_http):
    mock_http.get(f"{IBGE}/estados/SP/municipios").mock(side_effect=httpx.ConnectError("reset"))

    assert sincronizar(client, fonte="ibge")["ibge"]["status"] == "falha"
    resposta = client.get("/api/municipios/3550308/estabelecimentos")
    assert resposta.status_code == 200
    assert resposta.json()["total"] == 2
