# CLAUDE.md

Contexto do projeto para o Claude Code. Leia também `aula-03-claude-code/PRD.md` antes de qualquer mudança no pipeline.

## O projeto

Imersão Jornada de Dados: e-commerce brasileiro no Databricks Free Edition, em 4 aulas. Pipeline medalhão no catálogo `ecommerce` (schemas `bronze`, `silver` e `gold`; os arquivos brutos ficam no volume `ecommerce.bronze.arquivos`), dashboards AI/BI e um Genie space. Tudo é implantado como Declarative Automation Bundle (`databricks.yml`).

## Estrutura

- `aula-01-sql-dashboard/`: notebooks da Aula 1 (os CSVs sobem pela interface direto em `ecommerce.bronze.*`) e dashboard sobre a bronze. A partir da Aula 2, o Job sobrescreve essas tabelas bronze, agora com metadados de ingestão.
- `aula-02-python-engenharia/`: esquenta de Python (exercícios e gabarito) e a ingestão (`01_ingestao_bronze.py` com lacunas para a aula e `01_ingestao_bronze_gabarito.py` completo, que é o executado pelo Job): Storage do Supabase via boto3, protocolo S3. A Aula 2 termina na bronze.
- `aula-03-claude-code/`: transformação como Lakeflow Declarative Pipeline em `pipeline/` (`silver/*.py` e `gold/*.sql`, um arquivo por tabela), PRD, testes entre tabelas (`testes/03_testes_qualidade.py`) e dashboard sobre `gold`.
- `aula-04-genie/`: a aula em 2 prompts (`prompts/`: 3 dashboards, um por diretoria, e o agente do Genie testado com as perguntas de `perguntas_demo.md`), o gabarito dos dashboards (`dashboards/*.lvdash.json`) e do Genie space (`genie/diretoria_ecommerce.geniespace.json`), e a conferência dos comentários da gold (que moram no pipeline).
- `resources/`: Job, pipeline (`transformacao.pipeline.yml`), dashboards e Genie em YAML. Caminhos relativos começam com `../`.
- `dados/`: CSV e Parquet de origem.

## Comandos

Sempre passe o perfil da CLI (`-p <perfil>`); não assuma um perfil padrão.

```bash
databricks bundle validate --strict -t dev -p <perfil>
databricks bundle deploy -t dev -p <perfil>
databricks bundle run pipeline_ecommerce -t dev -p <perfil>
databricks experimental aitools tools query -p <perfil> -- "SELECT ..."
```

`dev` prefixa os recursos com `[dev usuario]` e pausa o agendamento. Faça deploy em `prod` só quando o usuário pedir.

## Convenções

- Nomes de tabelas e colunas em português, `snake_case`, sem acento.
- Notebooks no formato *source*: primeira linha `# Databricks notebook source` (Python) ou `-- Databricks notebook source` (SQL); células separadas por `COMMAND ----------`; texto em células `MAGIC %md`, em português e explicando o porquê.
- Python lê o catálogo do widget `catalogo`; notebooks SQL usam `USE CATALOG IDENTIFIER(:catalogo)` depois de criar o widget numa célula `%python`.
- Arquivos do pipeline não são notebooks: Python com `from pyspark import pipelines as dp` ou SQL puro, com o porquê em comentários no topo. Nomes sempre `schema.tabela`, sem catálogo (o pipeline usa `${var.catalogo}`).
- Silver em PySpark (`@dp.materialized_view` + expectations), gold em SQL (`CREATE OR REFRESH MATERIALIZED VIEW`). Materialized view, não streaming table: a bronze é sobrescrita a cada execução.
- Problema de qualidade conhecido é marcado em coluna e medido com `@dp.expect` (warn), nunca descartado; `expect_all_or_fail` só para o que nunca pode acontecer.
- Comentários da gold ficam na definição da materialized view (`COMMENT` na tabela e em cada coluna), para sobreviver ao refresh. Coluna nova na gold exige comentário; o teste `gold: toda coluna tem comentário` falha sem ele.
- Toda tabela gold nova precisa de teste em `testes/03_testes_qualidade.py` (regras linha a linha vão em expectations; o notebook testa chave, reconciliação e limites entre tabelas).
- Na Free Edition, `CREATE CATALOG` funciona por SQL, mas não pela API REST (falta storage root). Não troque o SQL por chamada de API.

## Números de referência (para validar mudanças)

- Receita total: R$ 974.077,28 (3.020 vendas); deve ser igual na silver e nas golds `vendas_temporais`, `vendas_produtos`, `clientes_segmentacao` e `vendas_detalhadas`.
- Bronze é gravada pela ingestão da Aula 2 direto do bucket `Datalake`, sem colunas de controle.
- 20 vendas de produtos não cadastrados (R$ 4.240,01); 5 vendas antes da criação do produto (R$ 325,88); 55 preços de concorrente suspeitos; 11 clientes com pronome de tratamento.
- Segmentos: 10 VIP, 25 TOP_TIER e 15 REGULAR.
- 35 produtos mais caros que todos os concorrentes: 20 confirmados (R$ 161.375,09 de receita) e 15 com preço suspeito, todos de Tênis e sem venda. Dashboards e Genie separam os dois grupos.
