"""Lista quem tem habilitação no processo transexualizador (30.01, 30.02, 30.03) num estado,
lendo o arquivo oficial de habilitações do CNES (arquivo HB) no FTP do DATASUS.

Precisa rodar numa máquina no Brasil: o DATASUS recusa conexões de fora.

    pip install -r scripts/requirements-habilitacoes.txt
    python scripts/habilitacoes_cnes.py --uf SP

Imprime a tabela e grava scripts/saida/habilitacoes_<UF>_<AAMM>.json.
"""

import argparse
import ftplib
import json
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

FTP_HOST = "ftp.datasus.gov.br"
FTP_PASTA = "/dissemin/publicos/CNES/200508_/Dados/HB"
CODIGOS = {"3001": "30.01", "3002": "30.02", "3003": "30.03"}
API_CNES = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos/{}"


def escolher_arquivo(nomes: list[str], uf: str, competencia: str | None = None) -> str:
    """HBSP2509.dbc = SP, competência 09/2025. Sem competência, pega a mais recente."""
    padrao = re.compile(rf"^HB{uf}(\d{{2}})(\d{{2}})\.dbc$", re.IGNORECASE)
    achados = {}
    for nome in nomes:
        m = padrao.match(Path(nome).name)
        if m:
            achados[m.group(1) + m.group(2)] = Path(nome).name
    if not achados:
        raise SystemExit(f"Nenhum arquivo HB{uf}*.dbc em {FTP_HOST}{FTP_PASTA}")
    if competencia:
        if competencia not in achados:
            raise SystemExit(f"Competência {competencia} não encontrada. Disponíveis: {', '.join(sorted(achados)[-6:])}")
        return achados[competencia]
    return achados[max(achados)]


def filtrar(registros, codigos: dict[str, str] = CODIGOS) -> list[dict]:
    """Fica com as linhas cujo código de habilitação é do processo transexualizador.
    Não depende do nome da coluna: o DATASUS já mudou o layout do HB."""
    saida = []
    for registro in registros:
        dados = {k: (str(v).strip() if v is not None else None) for k, v in dict(registro).items()}
        coluna = next((k for k, v in dados.items() if v in codigos and k.upper() != "CNES"), None)
        if coluna:
            saida.append({"cnes": dados.get("CNES"), "codigo": codigos[dados[coluna]], "coluna_codigo": coluna, "bruto": dados})
    return sorted(saida, key=lambda r: (r["codigo"], r["cnes"] or ""))


def baixar(nome: str, destino: Path) -> None:
    with ftplib.FTP(FTP_HOST, timeout=120) as ftp:
        ftp.login()
        ftp.cwd(FTP_PASTA)
        with destino.open("wb") as arquivo:
            ftp.retrbinary(f"RETR {nome}", arquivo.write)


def nome_no_cnes(cnes: str) -> str | None:
    try:
        pedido = urllib.request.Request(API_CNES.format(int(cnes)), headers={"User-Agent": "aquenda-soa/1.0"})
        with urllib.request.urlopen(pedido, timeout=30) as resposta:
            dados = json.load(resposta)
        return dados.get("nome_fantasia") or dados.get("nome_razao_social")
    except Exception:  # noqa: BLE001 - o nome é só para conferência
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--uf", default="SP")
    parser.add_argument("--competencia", help="AAMM, ex.: 2509. Padrão: a mais recente.")
    args = parser.parse_args(argv)
    uf = args.uf.upper()

    import pyreaddbc  # noqa: PLC0415 - só quem roda o script precisa instalar
    from dbfread import DBF  # noqa: PLC0415

    with ftplib.FTP(FTP_HOST, timeout=120) as ftp:
        ftp.login()
        ftp.cwd(FTP_PASTA)
        nome = escolher_arquivo(ftp.nlst(), uf, args.competencia)
    competencia = re.search(r"(\d{4})\.dbc$", nome, re.IGNORECASE).group(1)
    print(f"Arquivo oficial: ftp://{FTP_HOST}{FTP_PASTA}/{nome}")

    with tempfile.TemporaryDirectory() as pasta:
        dbc, dbf = Path(pasta) / nome, Path(pasta) / "hb.dbf"
        baixar(nome, dbc)
        pyreaddbc.dbc2dbf(str(dbc), str(dbf))
        linhas = filtrar(DBF(str(dbf), encoding="latin-1"))

    for linha in linhas:
        linha["nome"] = nome_no_cnes(linha["cnes"]) if linha["cnes"] else None
        linha["arquivo"] = nome

    print(f"\n{len(linhas)} habilitação(ões) do processo transexualizador em {uf}:\n")
    for linha in linhas:
        b = linha["bruto"]
        print(f"  {linha['codigo']}  CNES {linha['cnes']}  mun {b.get('CODUFMUN')}  {linha['nome'] or '(nome não encontrado)'}")
        extras = {k: v for k, v in b.items() if k not in {"CNES", "CODUFMUN", linha["coluna_codigo"]} and v}
        print(f"         {extras}")

    saida = Path(__file__).parent / "saida" / f"habilitacoes_{uf}_{competencia}.json"
    saida.parent.mkdir(exist_ok=True)
    saida.write_text(json.dumps(linhas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGravado em {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
