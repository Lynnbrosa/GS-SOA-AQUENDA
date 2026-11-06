"""Partes do script de habilitações que não dependem do FTP do DATASUS."""

import pytest

from scripts.habilitacoes_cnes import escolher_arquivo, filtrar


def test_escolhe_a_competencia_mais_recente_da_uf():
    nomes = ["HBSP2508.dbc", "HBSP2509.dbc", "HBRJ2510.dbc", "hbsp2412.dbc", "LEIAME.txt"]
    assert escolher_arquivo(nomes, "SP") == "HBSP2509.dbc"
    assert escolher_arquivo(nomes, "SP", "2412") == "hbsp2412.dbc"
    with pytest.raises(SystemExit):
        escolher_arquivo(nomes, "MG")
    with pytest.raises(SystemExit):
        escolher_arquivo(nomes, "SP", "2001")


def test_filtra_so_o_processo_transexualizador_sem_depender_do_nome_da_coluna():
    registros = [
        {"CNES": "2078015", "CODUFMUN": "355030", "SGRUPHAB": "3001", "PORTARIA": "2803"},
        {"CNES": "1234567", "CODUFMUN": "355030", "SGRUPHAB": "0801"},
        {"CNES": "7654321", "CODUFMUN": "350950", "HABILIT": "3002 "},
        {"CNES": "3001", "CODUFMUN": "355030", "SGRUPHAB": "1712"},
    ]
    linhas = filtrar(registros)
    assert [(x["cnes"], x["codigo"]) for x in linhas] == [("2078015", "30.01"), ("7654321", "30.02")]
    assert linhas[1]["coluna_codigo"] == "HABILIT"
