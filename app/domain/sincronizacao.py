"""Registro de cada vez que a API foi buscar dados numa fonte externa.

É esse histórico que decide se o cache ainda vale e que mostra ao app,
em GET /api/fontes, de quando é a informação que ele está vendo.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain.comum import garantir_utc
from app.domain.enums import NomeFonte, StatusSincronizacao


@dataclass
class Sincronizacao:
    fonte: NomeFonte
    iniciada_em: datetime
    status: StatusSincronizacao
    terminada_em: datetime | None = None
    itens: int = 0
    mensagem: str | None = None
    id: int | None = field(default=None)

    def __post_init__(self) -> None:
        self.iniciada_em = garantir_utc(self.iniciada_em)
        if self.terminada_em:
            self.terminada_em = garantir_utc(self.terminada_em)

    @property
    def sucesso(self) -> bool:
        return self.status == StatusSincronizacao.SUCESSO


def cache_valido(ultima_com_sucesso: Sincronizacao | None, agora: datetime, minutos: int) -> bool:
    """O cache vale se a última coleta boa terminou há menos de `minutos`."""
    if ultima_com_sucesso is None or ultima_com_sucesso.terminada_em is None:
        return False
    return garantir_utc(agora) - ultima_com_sucesso.terminada_em < timedelta(minutes=minutos)
