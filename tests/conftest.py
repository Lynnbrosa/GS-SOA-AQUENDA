"""Base dos testes: banco SQLite novo por teste (migrado pelo Alembic), relógio controlado
e rede bloqueada. Toda resposta externa vem de tests/fixtures."""

import json
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import respx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"

ADZUNA = "https://api.adzuna.com/v1/api/jobs/br/search"
GUPY = "https://portal.gupy.io/api/job-search/jobs"
CNES = "https://apidadosabertos.saude.gov.br/cnes"
IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades"


def carregar(nome: str):
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    """Se algum teste escapar do respx e tentar a internet, falha na hora."""

    def bloquear(*args, **kwargs):
        raise RuntimeError("Teste tentou acessar a rede. Use uma resposta gravada em tests/fixtures.")

    monkeypatch.setattr(socket, "create_connection", bloquear)
    monkeypatch.setattr(socket.socket, "connect", bloquear)


class RelogioDeTeste:
    def __init__(self) -> None:
        self.agora = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.agora

    def avancar(self, **delta) -> None:
        self.agora += timedelta(**delta)


@pytest.fixture
def relogio() -> RelogioDeTeste:
    return RelogioDeTeste()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'teste.db'}",
        ambiente="teste",
        adzuna_app_id="id-de-teste",
        adzuna_app_key="chave-de-teste",
        chave_operador="",
    )


@pytest.fixture
def mock_http():
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
def client(settings, relogio, mock_http):
    with TestClient(create_app(settings, relogio)) as c:
        yield c


@pytest.fixture
def fontes_ok(mock_http):
    """Todas as fontes respondendo com as gravações."""
    rotas = {
        "adzuna": mock_http.get(url__startswith=f"{ADZUNA}/1").respond(200, json=carregar("adzuna_busca.json")),
        # Buscas da Gupy: as duas primeiras com as respostas montadas (casos de borda), o resto vazio.
        "gupy_afirmativa": mock_http.get(GUPY, params={"jobName": "trans"}).respond(
            200, json=carregar("gupy_busca_afirmativa.json")),
        "gupy_trans": mock_http.get(GUPY, params={"jobName": "travesti"}).respond(
            200, json=carregar("gupy_busca_pessoas_trans.json")),
        **{
            f"gupy_vazia_{termo}": mock_http.get(GUPY, params={"jobName": termo}).respond(
                200, json={"data": [], "pagination": {}})
            for termo in ("transgênero", "LGBT", "LGBTQIA", "não binária")
        },
        "cnes": mock_http.get(f"{CNES}/estabelecimentos/2078015").respond(
            200, json=carregar("cnes_estabelecimento_2078015.json")),
        "cnes_ipq": mock_http.get(f"{CNES}/estabelecimentos/2812703").respond(
            200, json=carregar("cnes_estabelecimento_2812703.json")),
        "ibge": mock_http.get(f"{IBGE}/estados/SP/municipios").respond(200, json=carregar("ibge_municipios_sp.json")),
    }
    return rotas
