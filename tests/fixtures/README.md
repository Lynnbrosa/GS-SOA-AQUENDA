# Respostas gravadas para os testes

Os testes nunca usam a rede: toda chamada HTTP é atendida a partir destes arquivos (via `respx`),
e o `conftest.py` derruba qualquer tentativa de abrir conexão.

| Arquivo | Origem |
|---|---|
| `cnes_estabelecimento_2078015.json` | **Gravado** de `GET https://apidadosabertos.saude.gov.br/cnes/estabelecimentos/2078015` em 06/11/2026. O campo `endereco_email_estabelecimento` foi apagado (`null`) porque é um e-mail pessoal. |
| `cnes_estabelecimento_inexistente.json` | **Gravado** do mesmo endpoint com o código `1` (HTTP 404). |
| `adzuna_401.json` | **Gravado** de `GET https://api.adzuna.com/v1/api/jobs/br/search/1` com chave inválida (HTTP 401). |
| `adzuna_busca.json` | **Montado** no formato documentado em developer.adzuna.com (não havia chave válida na gravação). Empresas são fictícias ("Empresa Exemplo"). |
| `gupy_busca_*.json` | **Montado** no formato do portal público da Gupy. Na gravação, o endpoint respondeu 404 a partir do servidor de desenvolvimento. Empresas fictícias. |
| `ibge_municipios_sp.json` | **Montado** no formato do IBGE Localidades, com códigos IBGE reais. O servidor do IBGE recusou a conexão na gravação. Inclui um município sem `microrregiao` (acontece com municípios novos) e um item quebrado. |

Para regravar quando houver chave e acesso, rode a sincronização (`python -m app.cli sincronizar --forcar`)
e copie as respostas para cá, apagando campos pessoais.
