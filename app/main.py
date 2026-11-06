"""Ponto de entrada: `uvicorn app.main:app --port 8000`."""

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.erros import registrar_tratadores
from app.api.routers import fontes, localidades, vagas
from app.config import Settings, get_settings
from app.domain.comum import agora_utc
from app.infrastructure.db.migracoes import migrar
from app.infrastructure.db.sessao import criar_engine, criar_fabrica
from app.infrastructure.fontes.governo import CnesFonte, IbgeFonte
from app.infrastructure.fontes.http import criar_cliente
from app.infrastructure.fontes.vagas import AdzunaFonte, GupyFonte

DESCRICAO = """
Serviço do **Aquenda** (GS CitizenTech FIAP 2026.2) que junta, num lugar só:

- **Vagas afirmativas** para a comunidade LGBTQIAPN+: Adzuna (API oficial), Gupy (portal público)
  e a curadoria do grupo (Transcidadania, TransEmpregos). *A candidatura é sempre no site de origem.*
- **Estabelecimentos do CNES** com a habilitação 30.02 (processo transexualizador) e **municípios do IBGE**.

Cada registro guarda a **fonte** e **quando foi coletado**. Se uma fonte cair, a API segue
respondendo com o que tem no banco e mostra a falha em `GET /api/fontes`.

Erros seguem o formato ProblemDetails (RFC 7807), como a API C# do grupo.
"""

TAGS = [
    {"name": "Vagas", "description": "Vagas de emprego agregadas. Consumidas pela aba *vagas* do app."},
    {"name": "Municípios e CNES", "description": "Onde fazer o processo transexualizador pelo SUS."},
    {"name": "Fontes e saúde", "description": "Estado das fontes externas, sincronização e health check."},
]


def create_app(settings: Settings | None = None, relogio: Callable[[], datetime] = agora_utc) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        if settings.migrar_ao_iniciar:
            migrar(settings.database_url)
        engine = criar_engine(settings.database_url)
        cliente = criar_cliente(settings)
        app.state.settings = settings
        app.state.relogio = relogio
        app.state.fabrica = criar_fabrica(engine)
        app.state.fontes_vagas = [AdzunaFonte(cliente, settings), GupyFonte(cliente, settings)]
        app.state.fonte_cnes = CnesFonte(cliente, settings)
        app.state.fonte_ibge = IbgeFonte(cliente, settings)
        try:
            yield
        finally:
            cliente.close()
            engine.dispose()

    app = FastAPI(
        title="Aquenda · Serviço de vagas e CNES",
        version="1.0.0",
        description=DESCRICAO,
        openapi_tags=TAGS,
        lifespan=ciclo_de_vida,
        contact={"name": "Grupo Aquenda · FIAP ES 3º ano"},
    )
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
    registrar_tratadores(app)
    app.include_router(vagas.router)
    app.include_router(localidades.router)
    app.include_router(fontes.router)

    @app.get("/", include_in_schema=False)
    def raiz():
        return RedirectResponse("/docs")

    app.openapi = lambda: _openapi_com_erros_reais(app)
    return app


def _openapi_com_erros_reais(app: FastAPI) -> dict:
    """O FastAPI documenta validação como 422 no formato dele. Esta API responde 400 em
    ProblemDetails (ver api/erros.py), então o Swagger passa a mostrar o que acontece de verdade."""
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    esquema = get_openapi(title=app.title, version=app.version, description=app.description,
                          routes=app.routes, tags=app.openapi_tags, contact=app.contact)
    problema = {"application/problem+json": {"schema": {"$ref": "#/components/schemas/Problema"}}}
    for operacoes in esquema.get("paths", {}).values():
        for operacao in operacoes.values():
            respostas = operacao.get("responses", {})
            if respostas.pop("422", None) is not None:
                respostas.setdefault("400", {"description": "Parâmetro inválido"})
            for codigo, resposta in respostas.items():
                if codigo[0] in "45":
                    resposta["content"] = problema
    esquemas = esquema.get("components", {}).get("schemas", {})
    for nome in ("HTTPValidationError", "ValidationError"):
        esquemas.pop(nome, None)
    app.openapi_schema = esquema
    return esquema


app = create_app()
