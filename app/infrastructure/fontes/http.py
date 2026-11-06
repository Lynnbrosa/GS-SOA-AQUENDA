"""Cliente HTTP compartilhado pelas fontes e a regra única de "a fonte falhou"."""

import logging
from typing import Any

import httpx

from app.application.portas import FonteIndisponivel
from app.config import Settings

log = logging.getLogger(__name__)

# O httpx registra a URL inteira em INFO, e a Adzuna recebe app_key na URL.
# Abaixo de WARNING nada disso vai para o log da VM.
for _nome in ("httpx", "httpcore"):
    logging.getLogger(_nome).setLevel(logging.WARNING)


def criar_cliente(settings: Settings) -> httpx.Client:
    return httpx.Client(
        timeout=settings.http_timeout_segundos,
        headers={"User-Agent": settings.http_user_agent, "Accept": "application/json"},
        follow_redirects=True,
        # trust_env (padrão) mantém HTTPS_PROXY e SSL_CERT_FILE do servidor funcionando.
    )


def get_json(cliente: httpx.Client, nome: str, url: str, *, params: dict | None = None,
             aceitar_404: bool = False) -> Any:
    """GET que devolve JSON ou levanta FonteIndisponivel com uma mensagem que dá para mostrar."""
    try:
        resposta = cliente.get(url, params=params)
    except httpx.TimeoutException as erro:
        raise FonteIndisponivel(f"{nome} não respondeu a tempo.") from erro
    except httpx.HTTPError as erro:
        raise FonteIndisponivel(f"{nome} fora do ar ou bloqueado ({type(erro).__name__}).") from erro

    if aceitar_404 and resposta.status_code == 404:
        return None
    if resposta.status_code in (401, 403):
        raise FonteIndisponivel(f"{nome} recusou o acesso (HTTP {resposta.status_code}). Confira a chave.")
    if resposta.status_code == 429:
        raise FonteIndisponivel(f"{nome} pediu para esperar (HTTP 429).")
    if resposta.status_code >= 400:
        raise FonteIndisponivel(f"{nome} respondeu HTTP {resposta.status_code}.")
    try:
        return resposta.json()
    except ValueError as erro:
        raise FonteIndisponivel(f"{nome} respondeu algo que não é JSON.") from erro
