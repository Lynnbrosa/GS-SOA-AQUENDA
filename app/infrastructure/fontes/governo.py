"""Adaptadores das fontes públicas do governo: CNES (DATASUS) e IBGE Localidades."""

import logging
from datetime import date, datetime

import httpx

from app.application.portas import FonteIndisponivel
from app.config import Settings
from app.domain.comum import DomainError
from app.domain.localidades import EstabelecimentoCnes, Municipio
from app.infrastructure.fontes.http import get_json

log = logging.getLogger(__name__)


def _texto(valor) -> str | None:
    texto = str(valor).strip() if valor is not None else ""
    return texto or None


class CnesFonte:
    """API de dados abertos do Ministério da Saúde: /cnes/estabelecimentos/{codigo}."""

    def __init__(self, cliente: httpx.Client, settings: Settings) -> None:
        self._cliente = cliente
        self._url = settings.cnes_url.rstrip("/")

    def url_publica(self, codigo_cnes: int) -> str:
        return f"{self._url}/estabelecimentos/{codigo_cnes}"

    def obter(self, codigo_cnes: int, agora: datetime) -> EstabelecimentoCnes | None:
        dados = get_json(self._cliente, "CNES", self.url_publica(codigo_cnes), aceitar_404=True)
        if dados is None:
            return None
        if not isinstance(dados, dict) or "codigo_cnes" not in dados:
            raise FonteIndisponivel("CNES mudou o formato da resposta.")
        try:
            atualizado = date.fromisoformat(dados["data_atualizacao"]) if dados.get("data_atualizacao") else None
        except ValueError:
            atualizado = None
        try:
            return EstabelecimentoCnes.criar(
                codigo_cnes=dados["codigo_cnes"],
                nome=_texto(dados.get("nome_fantasia")),
                razao_social=_texto(dados.get("nome_razao_social")),
                codigo_municipio=dados.get("codigo_municipio"),
                fonte=f"CNES/DATASUS ({self.url_publica(codigo_cnes)})",
                coletado_em=agora,
                logradouro=_texto(dados.get("endereco_estabelecimento")),
                numero=_texto(dados.get("numero_estabelecimento")),
                bairro=_texto(dados.get("bairro_estabelecimento")),
                cep=_texto(dados.get("codigo_cep_estabelecimento")),
                telefone=_texto(dados.get("numero_telefone_estabelecimento")),
                latitude=dados.get("latitude_estabelecimento_decimo_grau"),
                longitude=dados.get("longitude_estabelecimento_decimo_grau"),
                tipo_unidade=dados.get("codigo_tipo_unidade"),
                atende_sus=(dados.get("estabelecimento_faz_atendimento_ambulatorial_sus") == "SIM"),
                turno=_texto(dados.get("descricao_turno_atendimento")),
                atualizado_no_cnes=atualizado,
                # endereco_email_estabelecimento é ignorado de propósito: costuma ser e-mail pessoal.
            )
        except DomainError as erro:
            log.info("CNES %s descartado: %s", codigo_cnes, erro)
            return None


class IbgeFonte:
    """IBGE Localidades: /estados/{UF}/municipios."""

    def __init__(self, cliente: httpx.Client, settings: Settings) -> None:
        self._cliente = cliente
        self._url = settings.ibge_url.rstrip("/")

    def municipios(self, uf: str, agora: datetime) -> list[Municipio]:
        url = f"{self._url}/estados/{uf}/municipios"
        dados = get_json(self._cliente, "IBGE", url)
        if not isinstance(dados, list):
            raise FonteIndisponivel("IBGE mudou o formato da resposta.")
        municipios = []
        for item in dados:
            try:
                municipios.append(Municipio.criar(
                    codigo_ibge=item["id"], nome=item["nome"], uf=self._uf(item) or uf,
                    fonte=f"IBGE Localidades ({url})", coletado_em=agora,
                ))
            except (DomainError, KeyError, TypeError) as erro:
                log.info("IBGE: município descartado (%s)", erro)
        return municipios

    @staticmethod
    def _uf(item: dict) -> str | None:
        """A UF aparece em dois caminhos; alguns municípios novos vêm sem microrregião."""
        try:
            return item["microrregiao"]["mesorregiao"]["UF"]["sigla"]
        except (KeyError, TypeError):
            pass
        try:
            return item["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]
        except (KeyError, TypeError):
            return None
