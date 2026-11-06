from enum import StrEnum


class OrigemVaga(StrEnum):
    """De onde a vaga veio. A candidatura é sempre no site de origem."""

    ADZUNA = "adzuna"
    GUPY = "gupy"
    CURADORIA = "curadoria"


class Modalidade(StrEnum):
    PRESENCIAL = "presencial"
    HIBRIDO = "hibrido"
    REMOTO = "remoto"
    NAO_INFORMADA = "nao_informada"


class NomeFonte(StrEnum):
    """Fontes externas que a API sincroniza."""

    ADZUNA = "adzuna"
    GUPY = "gupy"
    CNES = "cnes"
    IBGE = "ibge"


class StatusSincronizacao(StrEnum):
    SUCESSO = "sucesso"
    FALHA = "falha"
    NAO_CONFIGURADA = "nao_configurada"
    EM_CACHE = "em_cache"
