"""Peças pequenas que todo o domínio usa."""

import re
import unicodedata
from datetime import UTC, datetime


class DomainError(ValueError):
    """Regra de negócio violada. A API traduz para 422."""


def agora_utc() -> datetime:
    return datetime.now(UTC)


def normalizar(texto: str | None) -> str:
    """Minúsculas, sem acento e com espaços simples: base de toda busca por texto.

    Assim "São Paulo", "sao paulo" e "SAO  PAULO" caem no mesmo lugar, em qualquer banco.
    """
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def limpar_html(texto: str | None) -> str:
    """Tira tags e entidades simples das descrições que as fontes mandam em HTML."""
    if not texto:
        return ""
    sem_tags = re.sub(r"<[^>]+>", " ", texto)
    trocas = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'"}
    for antes, depois in trocas.items():
        sem_tags = sem_tags.replace(antes, depois)
    return re.sub(r"\s+", " ", sem_tags).strip()


def garantir_utc(momento: datetime) -> datetime:
    """SQLite devolve datas sem fuso. Tudo que guardamos é UTC, então reanexamos."""
    if momento.tzinfo is None:
        return momento.replace(tzinfo=UTC)
    return momento.astimezone(UTC)
