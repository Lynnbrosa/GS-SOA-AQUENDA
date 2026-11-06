# Respostas gravadas para os testes

Os testes nunca usam a rede: toda chamada HTTP é atendida a partir destes arquivos (via `respx`),
e o `conftest.py` derruba qualquer tentativa de abrir conexão.

| Arquivo | Origem |
|---|---|
| `cnes_estabelecimento_2078015.json` | **Gravado** de `GET https://apidadosabertos.saude.gov.br/cnes/estabelecimentos/2078015` em 06/11/2026. O campo `endereco_email_estabelecimento` foi apagado (`null`) porque é um e-mail pessoal. |
| `cnes_estabelecimento_inexistente.json` | **Gravado** do mesmo endpoint com o código `1` (HTTP 404). |
| `adzuna_401.json` | **Gravado** de `GET https://api.adzuna.com/v1/api/jobs/br/search/1` com chave inválida (HTTP 401). |
| `adzuna_real_pagina1.json` | **Gravado** da página 1 de `GET https://api.adzuna.com/v1/api/jobs/br/search/1` (mesmos parâmetros do adaptador) em 06/11/2026: 50 vagas reais. A chave não fica no arquivo, e o `app_id` que a Adzuna põe no `utm_source` dos links foi trocado por `APP_ID_REMOVIDO`. |
| `adzuna_busca.json` | **Montado** no formato real para casos de borda (vaga sem link, salário invertido, "transporte"). Empresas fictícias. |
| `gupy_real_*.json` | **Gravado** de `GET https://portal.gupy.io/api/job-search/jobs?jobName=<termo>&limit=100` em 06/11/2026, um arquivo por termo (37 vagas reais). Os textos foram varridos atrás de e-mails (nenhum encontrado). |
| `gupy_busca_*.json` | **Montado** no mesmo formato para casos de borda (link `javascript:`, vaga sem cidade, vaga não afirmativa). Empresas fictícias. |
| `ibge_municipios_sp.json` | **Montado** no formato do IBGE Localidades, com códigos IBGE reais. O servidor do IBGE recusou a conexão na gravação. Inclui um município sem `microrregiao` (acontece com municípios novos) e um item quebrado. |

Para regravar quando houver chave e acesso, rode a sincronização (`python -m app.cli sincronizar --forcar`)
e copie as respostas para cá, apagando campos pessoais.
