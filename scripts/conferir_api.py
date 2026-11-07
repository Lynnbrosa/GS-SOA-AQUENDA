"""Confere a API de ponta a ponta no banco de DATABASE_URL (SQLite ou PostgreSQL).

Aplica as migrações, sobe a API em processo (sem rede: nenhuma fonte externa é chamada) e
percorre o CRUD de empresas e a chave estrangeira vaga -> empresa. Imprime cada chamada e
sai com código 1 se algo não bater. O CI roda este script contra um PostgreSQL 16.

    DATABASE_URL=postgresql+psycopg://aquenda:senha@localhost:5432/aquenda_soa python -m scripts.conferir_api
"""

import json
import logging
import os
import sys

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.config import Settings
from app.infrastructure.db.migracoes import migrar
from app.main import create_app

PASSOS: list[str] = []


def chamar(c: TestClient, metodo: str, rota: str, esperado: int, **kw):
    r = c.request(metodo, rota, **kw)
    corpo = r.json() if r.content else None
    resumo = json.dumps(corpo, ensure_ascii=False)[:300] if corpo is not None else ""
    print(f"{metodo:<6} {rota:<40} -> {r.status_code}  {resumo}")
    if r.status_code != esperado:
        print(f"ERRO: esperava {esperado}", file=sys.stderr)
        sys.exit(1)
    return corpo


def main() -> None:
    url = os.environ.get("DATABASE_URL", "sqlite:///./aquenda_soa.db")
    banco = url.split("://", 1)[0]
    print(f"# banco: {banco}")
    migrar(url)
    engine = create_engine(url)
    with engine.connect() as conexao:
        versao = conexao.scalar(text("SELECT version_num FROM alembic_version"))
    chave = inspect(engine).get_foreign_keys("vagas")[0]
    print(f"# migrações aplicadas até {versao}; chave estrangeira {chave['name']}: "
          f"vagas.{chave['constrained_columns'][0]} -> {chave['referred_table']}.id "
          f"(ON DELETE {chave['options'].get('ondelete')})\n")

    settings = Settings(_env_file=None, database_url=url, ambiente="desenvolvimento", migrar_ao_iniciar=False)
    app = create_app(settings)
    for ruidoso in ("httpx", "httpx2", "alembic"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    with TestClient(app) as c:
        chamar(c, "GET", "/health", 200)
        empresas = chamar(c, "GET", "/api/empresas", 200)
        chamar(c, "GET", "/api/vagas?afirmativa=true&tamanho=5", 200)
        nova = chamar(c, "POST", "/api/empresas", 201, json={
            "nome": "Casa 1 (conferência)", "site": "https://www.casaum.org",
            "compromisso": "Centro de acolhida e cultura LGBTQIAPN+."})
        eid = nova["id"]
        chamar(c, "GET", f"/api/empresas/{eid}", 200)
        chamar(c, "PUT", f"/api/empresas/{eid}", 200, json={"nome": "Casa Um (conferência)", "site": None})
        chamar(c, "POST", "/api/empresas", 422, json={"nome": "CASA UM (conferência)"})
        chamar(c, "POST", "/api/empresas", 400, json={"nome": ""})
        chamar(c, "DELETE", f"/api/empresas/{eid}", 200)
        chamar(c, "GET", f"/api/empresas/{eid}", 404)

        # a chave estrangeira em ação: apagar a empresa deixa a vaga no ar, sem empresa
        alvo = next((e for e in empresas["itens"] if e["vagas_ativas"]), None)
        if alvo:
            vaga = chamar(c, "GET", f"/api/vagas?empresa_id={alvo['id']}", 200)["itens"][0]
            removida = chamar(c, "DELETE", f"/api/empresas/{alvo['id']}", 200)
            depois = chamar(c, "GET", f"/api/vagas/{vaga['id']}", 200)
            if removida["vagas_desvinculadas"] < 1 or depois["empresa_id"] is not None:
                print("ERRO: a vaga devia ficar no ar com empresa_id nulo", file=sys.stderr)
                sys.exit(1)
            # devolve a empresa para não deixar o banco diferente do que estava
            refeita = chamar(c, "POST", "/api/empresas", 201, json={"nome": alvo["nome"], "site": alvo["site"],
                                                                      "compromisso": alvo["compromisso"]})
            with engine.begin() as conexao:
                conexao.execute(text("UPDATE vagas SET empresa_id = :e WHERE id = :v"),
                                {"e": refeita["id"], "v": vaga["id"]})
    print(f"\nok: CRUD de empresas e chave estrangeira conferidos no {banco}")


if __name__ == "__main__":
    main()
