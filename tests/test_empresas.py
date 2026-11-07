"""Empresas: regras do domínio, o CRUD pela API e a ligação vaga -> empresa (chave estrangeira)."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.domain.comum import DomainError
from app.domain.empresa import SEM_EMPRESA, Empresa
from app.main import create_app

AGORA = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
NOVA = {"nome": "Casa 1", "site": "https://www.casaum.org", "compromisso": "Centro de acolhida e cultura LGBTQIAPN+."}


# ------------------------------------------------------------- domínio (sem banco, sem HTTP)

def test_empresa_limpa_o_nome_e_guarda_a_chave_sem_acento():
    e = Empresa.criar(nome="  <b>Itaú</b>  Unibanco ", agora=AGORA)
    assert e.nome == "Itaú Unibanco"
    assert e.nome_busca == "itau unibanco"
    assert e.criada_em == e.atualizada_em == AGORA


@pytest.mark.parametrize("nome", ["", " ", "A", SEM_EMPRESA, "empresa NAO informada"])
def test_empresa_sem_nome_de_verdade_e_recusada(nome):
    with pytest.raises(DomainError):
        Empresa.criar(nome=nome, agora=AGORA)
    assert not Empresa.e_empresa(nome)


def test_site_so_http():
    assert Empresa.criar(nome="Casa 1", site="https://www.casaum.org", agora=AGORA).site == "https://www.casaum.org"
    assert Empresa.criar(nome="Casa 1", site="  ", agora=AGORA).site is None
    with pytest.raises(DomainError, match="http"):
        Empresa.criar(nome="Casa 1", site="javascript:alert(1)", agora=AGORA)


def test_atualizar_revalida_e_muda_a_data():
    e = Empresa.criar(nome="Casa 1", agora=AGORA)
    depois = datetime(2026, 11, 11, tzinfo=UTC)
    e.atualizar(nome="Casa Um", site=None, compromisso="Acolhida", agora=depois)
    assert (e.nome, e.compromisso, e.criada_em, e.atualizada_em) == ("Casa Um", "Acolhida", AGORA, depois)
    with pytest.raises(DomainError):
        e.atualizar(nome="", site=None, compromisso=None, agora=depois)


# ------------------------------------------------------------- CRUD pela API

def test_crud_completo(client):
    criada = client.post("/api/empresas", json=NOVA)
    assert criada.status_code == 201, criada.text
    corpo = criada.json()
    assert {k: corpo[k] for k in NOVA} == NOVA and corpo["vagas_ativas"] == 0
    eid = corpo["id"]

    assert client.get(f"/api/empresas/{eid}").json()["nome"] == "Casa 1"
    lista = client.get("/api/empresas", params={"nome": "casa"}).json()
    assert [e["nome"] for e in lista["itens"]] == ["Casa 1"] and lista["total"] == 1

    editada = client.put(f"/api/empresas/{eid}", json={"nome": "Casa Um", "site": None})
    assert editada.status_code == 200
    assert (editada.json()["nome"], editada.json()["site"], editada.json()["compromisso"]) == ("Casa Um", None, None)

    removida = client.delete(f"/api/empresas/{eid}")
    assert removida.status_code == 200 and removida.json() == {"id": eid, "vagas_desvinculadas": 0}
    assert client.get(f"/api/empresas/{eid}").status_code == 404
    assert client.delete(f"/api/empresas/{eid}").status_code == 404


def test_base_nova_ja_tem_as_empresas_da_curadoria(client):
    itens = client.get("/api/empresas").json()["itens"]
    assert [(e["nome"], e["vagas_ativas"]) for e in itens] == [("Prefeitura de São Paulo", 1), ("TransEmpregos", 1)]


def test_nome_repetido_sem_acento_ou_maiuscula_e_422(client):
    resposta = client.post("/api/empresas", json={"nome": "TRANSEMPREGOS"})
    assert resposta.status_code == 422
    assert resposta.headers["content-type"].startswith("application/problem+json")
    assert "Já existe" in resposta.json()["detail"]


def test_erros_de_entrada(client):
    assert client.post("/api/empresas", json={"nome": ""}).status_code == 400
    assert client.post("/api/empresas", json={"site": "https://x.org"}).status_code == 400
    assert client.post("/api/empresas", json={"nome": "Casa 1", "site": "ftp://x"}).status_code == 422
    assert client.put("/api/empresas/9999", json={"nome": "Casa 1"}).status_code == 404
    assert client.get("/api/empresas", params={"tamanho": 51}).status_code == 400


def test_apagar_a_empresa_nao_apaga_a_vaga(client):
    """ON DELETE SET NULL: a vaga continua no ar, sem empresa vinculada."""
    transempregos = next(e for e in client.get("/api/empresas").json()["itens"] if e["nome"] == "TransEmpregos")
    vagas = client.get("/api/vagas", params={"empresa_id": transempregos["id"]}).json()["itens"]
    assert [v["empresa"] for v in vagas] == ["TransEmpregos"]

    assert client.delete(f"/api/empresas/{transempregos['id']}").json()["vagas_desvinculadas"] == 1

    vaga = client.get(f"/api/vagas/{vagas[0]['id']}").json()
    assert vaga["empresa"] == "TransEmpregos" and vaga["empresa_id"] is None


def test_escrita_exige_chave_de_operador_fora_de_desenvolvimento(settings, relogio, mock_http):
    com_chave = settings.model_copy(update={"ambiente": "producao", "chave_operador": "segredo"})
    with TestClient(create_app(com_chave, relogio)) as c:
        assert c.get("/api/empresas").status_code == 200, "ler é livre"
        assert c.post("/api/empresas", json=NOVA).status_code == 401
        assert c.put("/api/empresas/1", json=NOVA, headers={"X-Chave-Operador": "errada"}).status_code == 401
        assert c.delete("/api/empresas/1").status_code == 401
        assert c.post("/api/empresas", json=NOVA, headers={"X-Chave-Operador": "segredo"}).status_code == 201


# ------------------------------------------------------------- sincronização liga vaga -> empresa

def test_sincronizacao_cria_a_empresa_uma_vez_e_liga_as_vagas(client, fontes_ok, relogio):
    assert client.post("/api/fontes/sincronizar").status_code == 200
    vagas = client.get("/api/vagas", params={"tamanho": 50}).json()["itens"]
    for v in vagas:
        if Empresa.e_empresa(v["empresa"]):
            assert v["empresa_id"] is not None, v["empresa"]
            assert client.get(f"/api/empresas/{v['empresa_id']}").json()["nome"].lower() == v["empresa"].lower()
        else:
            assert v["empresa_id"] is None
    antes = client.get("/api/empresas", params={"tamanho": 50}).json()["total"]

    relogio.avancar(hours=2)
    assert client.post("/api/fontes/sincronizar", params={"forcar": True}).status_code == 200
    assert client.get("/api/empresas", params={"tamanho": 50}).json()["total"] == antes, "não duplica empresa"
