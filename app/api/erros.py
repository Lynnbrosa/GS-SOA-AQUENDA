"""Toda exceção conhecida vira ProblemDetails (RFC 7807), como na API C#."""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.application.erros import ParametroInvalido, RecursoNaoEncontrado
from app.domain.comum import DomainError

log = logging.getLogger(__name__)

TIPO = "application/problem+json"


def problema(request: Request, status: int, titulo: str, detalhe: str | None = None, **extras) -> JSONResponse:
    corpo = {"type": "about:blank", "title": titulo, "status": status, "detail": detalhe,
             "instance": request.url.path, **extras}
    return JSONResponse(corpo, status_code=status, media_type=TIPO)


def registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(RecursoNaoEncontrado)
    async def _404(request: Request, erro: RecursoNaoEncontrado):
        return problema(request, 404, "Não encontrado", str(erro))

    @app.exception_handler(ParametroInvalido)
    async def _400(request: Request, erro: ParametroInvalido):
        return problema(request, 400, "Parâmetro inválido", str(erro))

    @app.exception_handler(DomainError)
    async def _422(request: Request, erro: DomainError):
        return problema(request, 422, "Regra de negócio", str(erro))

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, erro: RequestValidationError):
        erros = [
            {"campo": ".".join(str(p) for p in e["loc"] if p not in ("query", "path", "body")), "mensagem": e["msg"]}
            for e in erro.errors()
        ]
        return problema(request, 400, "Parâmetro inválido", "Confira os campos em 'erros'.", erros=erros)

    @app.exception_handler(HTTPException)
    async def _http(request: Request, erro: HTTPException):
        return problema(request, erro.status_code, erro.detail if isinstance(erro.detail, str) else "Erro",
                        None)

    @app.exception_handler(Exception)
    async def _500(request: Request, erro: Exception):
        log.exception("Erro não tratado em %s", request.url.path)
        return problema(request, 500, "Erro interno", "Algo deu errado do nosso lado.")
