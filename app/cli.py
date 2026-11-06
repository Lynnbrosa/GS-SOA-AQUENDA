"""Linha de comando para a VM: `python -m app.cli sincronizar [--fonte adzuna] [--forcar]`.

Feita para o timer do systemd: sai com código 1 se alguma fonte falhou,
para o monitoramento registrar, mas a API continua de pé com o cache.
"""

import argparse
import sys

from app.application.sincronizacao import PrazosCache, SincronizacaoService
from app.config import get_settings
from app.domain.comum import agora_utc
from app.domain.enums import NomeFonte, StatusSincronizacao
from app.infrastructure.db.migracoes import migrar
from app.infrastructure.db.sessao import criar_engine, criar_fabrica
from app.infrastructure.fontes.governo import CnesFonte, IbgeFonte
from app.infrastructure.fontes.http import criar_cliente
from app.infrastructure.fontes.vagas import AdzunaFonte, GupyFonte
from app.infrastructure.repositorios.sql import SqlUnidadeDeTrabalho


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    sinc = sub.add_parser("sincronizar", help="Busca dados novos nas fontes externas.")
    sinc.add_argument("--fonte", choices=[f.value for f in NomeFonte])
    sinc.add_argument("--forcar", action="store_true", help="Ignora o cache.")
    sub.add_parser("migrar", help="Aplica as migrações (alembic upgrade head).")
    args = parser.parse_args(argv)

    s = get_settings()
    migrar(s.database_url)
    if args.comando == "migrar":
        return 0

    engine = criar_engine(s.database_url)
    with criar_cliente(s) as cliente, criar_fabrica(engine)() as sessao:
        servico = SincronizacaoService(
            SqlUnidadeDeTrabalho(sessao),
            fontes_vagas=[AdzunaFonte(cliente, s), GupyFonte(cliente, s)],
            fonte_cnes=CnesFonte(cliente, s),
            fonte_ibge=IbgeFonte(cliente, s),
            relogio=agora_utc,
            prazos=PrazosCache(s.cache_minutos_vagas, s.cache_minutos_cnes, s.cache_minutos_ibge),
            uf_ibge=s.ibge_uf,
        )
        resultados = (
            [servico.sincronizar(NomeFonte(args.fonte), args.forcar)] if args.fonte
            else servico.sincronizar_todas(args.forcar)
        )
    for r in resultados:
        print(f"{r.fonte.value:8} {r.status.value:16} {r.itens:5} itens  {r.mensagem or ''}")
    return 1 if any(r.status == StatusSincronizacao.FALHA for r in resultados) else 0


if __name__ == "__main__":
    sys.exit(main())
