"""Regra que decide se uma vaga é afirmativa para a comunidade LGBTQIAPN+.

As fontes não têm um campo "vaga afirmativa". A decisão vem do texto que a empresa
escreveu, com fronteira de palavra para não confundir "trans" com "transporte".
"""

import re

from app.domain.comum import normalizar

_PADROES = [
    re.compile(r"\bafirmativ[ao]s?\b"),
    re.compile(r"\bpessoas? (trans|travestis?|transgeneros?|transexua(l|is)|nao binarias?)\b"),
    re.compile(r"\btravestis?\b"),
    re.compile(r"\btransgeneros?\b"),
    re.compile(r"\blgbt[a-z+]*\b"),
    re.compile(r"\btranscidadania\b"),
]


def termo_afirmativo(*textos: str | None) -> str | None:
    """Devolve o trecho que tornou a vaga afirmativa, ou None.

    Guardar o termo permite explicar no app por que a vaga aparece no filtro.
    """
    alvo = " ".join(normalizar(t) for t in textos if t)
    for padrao in _PADROES:
        achado = padrao.search(alvo)
        if achado:
            return achado.group(0)
    return None


def eh_afirmativa(*textos: str | None) -> bool:
    return termo_afirmativo(*textos) is not None
