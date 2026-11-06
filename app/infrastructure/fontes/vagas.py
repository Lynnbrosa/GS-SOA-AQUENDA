"""Adaptadores das fontes de vagas: Adzuna (API oficial) e Gupy (endpoint público do portal)."""

import logging
from datetime import datetime

import httpx

from app.application.portas import FonteIndisponivel
from app.config import Settings
from app.domain.comum import DomainError, normalizar
from app.domain.enums import Modalidade, NomeFonte, OrigemVaga
from app.domain.vaga import Vaga
from app.infrastructure.fontes.http import get_json

log = logging.getLogger(__name__)

UF_POR_NOME = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA", "mato grosso": "MT",
    "mato grosso do sul": "MS", "minas gerais": "MG", "para": "PA", "paraiba": "PB", "parana": "PR",
    "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR", "santa catarina": "SC", "sao paulo": "SP",
    "sergipe": "SE", "tocantins": "TO",
}


def _data_iso(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None


def _montar(vagas: list[Vaga], nome: str, criar) -> None:
    """Uma vaga malformada não derruba a coleta inteira: é descartada e registrada no log."""
    try:
        vagas.append(criar())
    except (DomainError, KeyError, TypeError, ValueError) as erro:
        log.info("%s: vaga descartada (%s)", nome, erro)


class AdzunaFonte:
    """API oficial da Adzuna (https://developer.adzuna.com). Precisa de app_id e app_key."""

    nome = NomeFonte.ADZUNA
    origem = OrigemVaga.ADZUNA
    TERMOS = "lgbt lgbtqia lgbtqiapn lgbti travesti travestis transgenero trans"
    PAGINAS = 2
    POR_PAGINA = 50

    def __init__(self, cliente: httpx.Client, settings: Settings) -> None:
        self._cliente = cliente
        self._s = settings

    def configurada(self) -> bool:
        return self._s.adzuna_configurada

    def buscar(self, agora: datetime) -> list[Vaga]:
        vagas: list[Vaga] = []
        for pagina in range(1, self.PAGINAS + 1):
            dados = get_json(self._cliente, "Adzuna", f"{self._s.adzuna_url}/{pagina}", params={
                "app_id": self._s.adzuna_app_id,
                "app_key": self._s.adzuna_app_key,
                "results_per_page": self.POR_PAGINA,
                "what_or": self.TERMOS,
                "where": "São Paulo",
                "content-type": "application/json",
            })
            if not isinstance(dados, dict) or not isinstance(dados.get("results"), list):
                raise FonteIndisponivel("Adzuna mudou o formato da resposta.")
            for item in dados["results"]:
                _montar(vagas, "Adzuna", lambda item=item: self._converter(item, agora))
            if len(dados["results"]) < self.POR_PAGINA:
                break
        return vagas

    def _converter(self, item: dict, agora: datetime) -> Vaga:
        area = (item.get("location") or {}).get("area") or []
        # area vem como ["Brasil", "São Paulo" (estado), "São Paulo" (cidade), ...]
        uf = UF_POR_NOME.get(normalizar(area[1])) if len(area) > 1 else None
        cidade = area[-1] if len(area) > 2 else None
        return Vaga.criar(
            origem=self.origem,
            id_externo=str(item["id"]),
            titulo=item["title"],
            empresa=(item.get("company") or {}).get("display_name"),
            descricao=item.get("description"),
            url_candidatura=item["redirect_url"],
            fonte="Adzuna (API oficial)",
            coletada_em=agora,
            cidade=cidade,
            uf=uf,
            publicada_em=_data_iso(item.get("created")),
            salario_min=item.get("salary_min"),
            salario_max=item.get("salary_max"),
        )


class GupyFonte:
    """Rota pública que o portal de vagas da Gupy usa na própria busca. Não é API oficial:
    por isso o cache de 60 minutos e a URL configurável em GUPY_URL."""

    nome = NomeFonte.GUPY
    origem = OrigemVaga.GUPY
    # Testados no portal em 06/11/2026; "diversidade" e "afirmativa" trazem muito ruído (PCD, 50+).
    TERMOS = ("trans", "travesti", "transgênero", "LGBT", "LGBTQIA", "não binária")
    LIMITE = 100

    _MODALIDADES = {"remote": Modalidade.REMOTO, "hybrid": Modalidade.HIBRIDO, "on-site": Modalidade.PRESENCIAL}

    def __init__(self, cliente: httpx.Client, settings: Settings) -> None:
        self._cliente = cliente
        self._s = settings

    def configurada(self) -> bool:
        return bool(self._s.gupy_url)

    def buscar(self, agora: datetime) -> list[Vaga]:
        por_id: dict[str, Vaga] = {}
        for termo in self.TERMOS:
            dados = get_json(self._cliente, "Gupy", self._s.gupy_url,
                             params={"jobName": termo, "offset": 0, "limit": self.LIMITE})
            if not isinstance(dados, dict) or not isinstance(dados.get("data"), list):
                raise FonteIndisponivel("Gupy mudou o formato da resposta.")
            lote: list[Vaga] = []
            for item in dados["data"]:
                _montar(lote, "Gupy", lambda item=item: self._converter(item, agora))
            for vaga in lote:
                por_id.setdefault(vaga.id_externo, vaga)
        return list(por_id.values())

    def _converter(self, item: dict, agora: datetime) -> Vaga:
        modalidade = self._MODALIDADES.get(item.get("workplaceType") or "")
        if modalidade is None and item.get("isRemoteWork"):
            modalidade = Modalidade.REMOTO
        return Vaga.criar(
            origem=self.origem,
            id_externo=str(item["id"]),
            titulo=item["name"],
            empresa=item.get("careerPageName"),
            descricao=item.get("description"),
            url_candidatura=item["jobUrl"],
            fonte="Gupy (portal público de vagas)",
            coletada_em=agora,
            cidade=item.get("city") or None,
            uf=UF_POR_NOME.get(normalizar(item.get("state"))),
            modalidade=modalidade,
            publicada_em=_data_iso(item.get("publishedDate")),
        )
