"""Contrato HTTP que o app Expo consome: filtros, status, erros e documentação."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def com_vagas(client, fontes_ok):
    assert client.post("/api/fontes/sincronizar").status_code == 200
    return client


def listar(client, **params):
    resposta = client.get("/api/vagas", params=params)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


# ------------------------------------------------------------- vagas

def test_base_nova_ja_tem_a_curadoria(client):
    pagina = listar(client)
    assert [v["titulo"].split(" · ")[0] for v in pagina["itens"]] == ["Transcidadania", "TransEmpregos"]
    assert all(v["afirmativa"] and v["origem"] == "curadoria" for v in pagina["itens"])


def test_curadoria_vem_primeiro_e_depois_as_mais_novas(com_vagas):
    itens = listar(com_vagas, tamanho=50)["itens"]
    origens = [v["origem"] for v in itens]
    assert origens[:2] == ["curadoria", "curadoria"]
    datas = [v["publicada_em"] for v in itens[2:]]
    assert datas == sorted(datas, reverse=True)


def test_filtro_afirmativa(com_vagas):
    afirmativas = listar(com_vagas, afirmativa="true", tamanho=50)["itens"]
    nao = listar(com_vagas, afirmativa="false", tamanho=50)["itens"]
    assert len(afirmativas) == 5 and all(v["afirmativa"] for v in afirmativas)
    assert {v["titulo"] for v in nao} == {"Motorista de transporte escolar", "Atendente de Loja"}


def test_filtro_texto_ignora_acento_e_procura_todas_as_palavras(com_vagas):
    assert {v["titulo"] for v in listar(com_vagas, texto="ANALISTA dados")["itens"]} == {
        "Analista de Dados Jr. - Vaga afirmativa para pessoas trans"}
    assert listar(com_vagas, texto="transformacao")["total"] == 0
    assert listar(com_vagas, texto="100%")["total"] == 0, "% não pode virar curinga"


def test_filtro_cidade_uf_modalidade_e_origem(com_vagas):
    assert listar(com_vagas, cidade="sao paulo", origem="gupy")["total"] == 2
    assert listar(com_vagas, uf="sp", origem="adzuna")["total"] == 2
    remotas = listar(com_vagas, modalidade="remoto")["itens"]
    assert [v["empresa"] for v in remotas] == ["Empresa Exemplo E"]
    assert listar(com_vagas, modalidade="hibrido")["total"] == 2


def test_paginacao(com_vagas):
    primeira = listar(com_vagas, tamanho=3, pagina=1)
    terceira = listar(com_vagas, tamanho=3, pagina=3)
    assert (primeira["total"], primeira["total_paginas"]) == (7, 3)
    assert len(primeira["itens"]) == 3 and len(terceira["itens"]) == 1
    assert listar(com_vagas, tamanho=3, pagina=9)["itens"] == []


@pytest.mark.parametrize("params", [
    {"tamanho": 0}, {"tamanho": 51}, {"pagina": 0}, {"modalidade": "teletransporte"},
    {"uf": "SPX"}, {"afirmativa": "talvez"}, {"origem": "linkedin"},
])
def test_filtro_invalido_responde_400_em_problem_details(client, params):
    resposta = client.get("/api/vagas", params=params)
    assert resposta.status_code == 400
    assert resposta.headers["content-type"] == "application/problem+json"
    corpo = resposta.json()
    assert corpo["title"] == "Parâmetro inválido" and corpo["erros"]


def test_detalhe_da_vaga_traz_fonte_coleta_e_aviso(com_vagas):
    vaga_id = listar(com_vagas, origem="adzuna", afirmativa="true")["itens"][0]["id"]
    detalhe = com_vagas.get(f"/api/vagas/{vaga_id}").json()
    assert detalhe["fonte"] == "Adzuna (API oficial)"
    assert detalhe["coletada_em"] == "2026-11-10T12:00:00Z"
    assert detalhe["termo_afirmativo"] == "pessoas trans"
    assert "site de origem" in detalhe["aviso"]
    assert detalhe["descricao"].startswith("Vaga afirmativa para pessoas trans")


def test_vaga_inexistente_404(client):
    resposta = client.get("/api/vagas/999")
    assert resposta.status_code == 404
    assert resposta.json() == {
        "type": "about:blank", "title": "Não encontrado", "status": 404,
        "detail": "Vaga 999 não existe ou já saiu do ar na fonte.", "instance": "/api/vagas/999",
    }
    assert client.get("/api/vagas/0").status_code == 400


# ------------------------------------------------------------- municípios e CNES

def test_estabelecimentos_do_municipio_com_habilitacao(client):
    corpo = client.get("/api/municipios/3550308/estabelecimentos").json()
    assert corpo["municipio"]["nome"] == "São Paulo"
    assert corpo["habilitacoes"] == ["30.01", "30.02", "30.03"]
    assert {e["codigo_cnes"]: e["habilitacoes"] for e in corpo["itens"]} == {2078015: ["30.01"], 2812703: ["30.01"]}
    assert all(e["fonte"].startswith("CNES/DATASUS") for e in corpo["itens"])

    so_ambulatorial = client.get("/api/municipios/3550308/estabelecimentos", params={"habilitacao": "30.02"}).json()
    assert (so_ambulatorial["habilitacoes"], so_ambulatorial["total"]) == (["30.02"], 0)
    todas = client.get("/api/municipios/3550308/estabelecimentos", params={"todas": "true"}).json()
    assert (todas["habilitacoes"], todas["total"]) == (None, 2)
    invalida = client.get("/api/municipios/3550308/estabelecimentos", params={"habilitacao": "99.99"})
    assert invalida.status_code == 400 and "30.01" in invalida.json()["detail"]


def test_municipio_sem_dados_responde_lista_vazia_e_codigo_errado_400(client):
    corpo = client.get("/api/municipios/3518800/estabelecimentos").json()
    assert corpo == {"codigo_ibge": 3518800, "municipio": None, "habilitacoes": ["30.01", "30.02", "30.03"],
                     "total": 0, "itens": []}
    assert client.get("/api/municipios/355030/estabelecimentos").status_code == 400
    assert client.get("/api/municipios/9950308/estabelecimentos").status_code == 400


def test_municipios_busca_por_nome_sem_acento(com_vagas):
    nomes = [m["nome"] for m in com_vagas.get("/api/municipios", params={"nome": "SAO paulo"}).json()]
    assert nomes == ["São Paulo"]
    assert com_vagas.get("/api/municipios/3550308").json()["codigo_cnes"] == 355030
    assert com_vagas.get("/api/municipios/3304557").status_code == 404
    assert com_vagas.get("/api/municipios", params={"uf": "S"}).status_code == 400


def test_estabelecimento_por_codigo(client):
    assert client.get("/api/cnes/estabelecimentos/2078015").json()["bairro"] == "CERQUEIRA CESAR"
    assert client.get("/api/cnes/estabelecimentos/1234567").status_code == 404
    assert client.get("/api/cnes/estabelecimentos/123456789").status_code == 400


# ------------------------------------------------------------- operador, saúde e documentação

def test_sincronizar_exige_chave_fora_de_desenvolvimento(settings, relogio, mock_http):
    producao = settings.model_copy(update={"ambiente": "producao", "chave_operador": ""})
    with TestClient(create_app(producao, relogio)) as c:
        assert c.post("/api/fontes/sincronizar").status_code == 503

    com_chave = settings.model_copy(update={"ambiente": "producao", "chave_operador": "segredo"})
    mock_http.get(url__regex=r".*").respond(503)
    with TestClient(create_app(com_chave, relogio)) as c:
        assert c.post("/api/fontes/sincronizar").status_code == 401
        assert c.post("/api/fontes/sincronizar", headers={"X-Chave-Operador": "errada"}).status_code == 401
        ok = c.post("/api/fontes/sincronizar", headers={"X-Chave-Operador": "segredo"})
        assert ok.status_code == 200
        assert {r["status"] for r in ok.json()} == {"falha"}
        assert c.get("/api/vagas").json()["total"] == 2, "leitura segue livre e com cache"


def test_health_e_raiz(client):
    assert client.get("/health").json() == {"status": "ok", "banco": "ok"}
    raiz = client.get("/", follow_redirects=False)
    assert raiz.status_code == 307 and raiz.headers["location"] == "/docs"


def test_swagger_documenta_todos_os_endpoints(client):
    assert client.get("/docs").status_code == 200
    esquema = client.get("/openapi.json").json()
    rotas = {(m.upper(), p) for p, ops in esquema["paths"].items() for m in ops}
    assert rotas == {
        ("GET", "/api/vagas"), ("GET", "/api/vagas/{vaga_id}"),
        ("GET", "/api/municipios"), ("GET", "/api/municipios/{codigo_ibge}"),
        ("GET", "/api/municipios/{codigo_ibge}/estabelecimentos"),
        ("GET", "/api/cnes/estabelecimentos/{codigo_cnes}"),
        ("GET", "/api/fontes"), ("POST", "/api/fontes/sincronizar"), ("GET", "/health"),
    }
    assert {t["name"] for t in esquema["tags"]} == {"Vagas", "Municípios e CNES", "Fontes e saúde"}
    filtros = {p["name"] for p in esquema["paths"]["/api/vagas"]["get"]["parameters"]}
    assert {"texto", "cidade", "afirmativa", "modalidade"} <= filtros
    assert "404" in esquema["paths"]["/api/vagas/{vaga_id}"]["get"]["responses"]
