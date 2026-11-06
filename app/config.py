"""Configuração lida do ambiente (contrato do grupo: porta 8000, DATABASE_URL, ADZUNA_*)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="sqlite:///./aquenda_soa.db")
    ambiente: str = Field(default="desenvolvimento")
    # Aplica `alembic upgrade head` na subida (igual à API C#). Na VM o build já roda o comando.
    migrar_ao_iniciar: bool = True

    # Adzuna: API oficial. Sem chave, a fonte fica "não configurada" e a API segue com o cache.
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_url: str = "https://api.adzuna.com/v1/api/jobs/br/search"

    # Gupy: endpoint público do portal de vagas. Configurável porque não é uma API oficial.
    gupy_url: str = "https://portal.api.gupy.io/api/job"

    cnes_url: str = "https://apidadosabertos.saude.gov.br/cnes"
    ibge_url: str = "https://servicodados.ibge.gov.br/api/v1/localidades"
    ibge_uf: str = "SP"

    # Quanto tempo o resultado de uma fonte vale antes de ela ser consultada de novo.
    cache_minutos_vagas: int = 60
    cache_minutos_cnes: int = 24 * 60
    cache_minutos_ibge: int = 7 * 24 * 60

    http_timeout_segundos: float = 15.0
    http_user_agent: str = "aquenda-soa/1.0 (GS CitizenTech FIAP)"

    chave_operador: str = ""

    @property
    def em_desenvolvimento(self) -> bool:
        return self.ambiente.lower() in {"desenvolvimento", "development", "dev", "teste"}

    @property
    def adzuna_configurada(self) -> bool:
        return bool(self.adzuna_app_id and self.adzuna_app_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
