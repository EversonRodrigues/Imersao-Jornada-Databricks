-- ============================================
-- Aula 1 · Setup e demonstração CSV × Tabela
-- Mesmas consultas do notebook 01_sql_e_dashboard.sql
-- ============================================

-- # 0. Setup
-- No Databricks os dados são organizados em três níveis, pelo **Unity Catalog**:
-- catálogo  →  schema  →  tabela / volume
-- ecommerce →  raw     →  vendas, produtos, clientes, preco_competidores
-- →  arquivos (volume: onde ficam os CSVs)
-- Vamos criar também os schemas `bronze`, `silver` e `gold`, que serão usados a partir da Aula 2.

CREATE CATALOG IF NOT EXISTS ecommerce COMMENT 'Imersão Jornada de Dados: e-commerce';

CREATE SCHEMA IF NOT EXISTS ecommerce.raw    COMMENT 'Dados como chegaram da origem';
CREATE SCHEMA IF NOT EXISTS ecommerce.bronze COMMENT 'Aula 2: ingestão com metadados';
CREATE SCHEMA IF NOT EXISTS ecommerce.silver COMMENT 'Aula 2: dados limpos e padronizados';
CREATE SCHEMA IF NOT EXISTS ecommerce.gold   COMMENT 'Aula 2: tabelas prontas para o negócio';

CREATE VOLUME IF NOT EXISTS ecommerce.raw.arquivos COMMENT 'Arquivos brutos (CSV, Parquet, JSON)';

-- ### Enviar os 4 CSVs para o volume
-- 1. Baixe os arquivos da pasta `dados/` do repositório: `produtos.csv`, `clientes.csv`, `vendas.csv` e `preco_competidores.csv`.
-- 2. No menu lateral, abra **Catalog → ecommerce → raw → arquivos**.
-- 3. Clique em **Upload to this volume** e arraste os 4 arquivos.
-- Confira se eles chegaram:

LIST '/Volumes/ecommerce/raw/arquivos/';

-- # 1. CSV × Tabela
-- Dá para consultar o arquivo direto com `read_files`. O Databricks lê o CSV e **adivinha** os tipos de cada coluna.

SELECT *
FROM read_files(
  '/Volumes/ecommerce/raw/arquivos/vendas.csv',
  format => 'csv',
  header => true
)
LIMIT 10;

-- Consultar o arquivo funciona, mas um arquivo não garante nada: qualquer um pode abrir o CSV e escrever "duas" na coluna de quantidade.
-- Uma **tabela Delta** tem um contrato (schema), guarda o histórico de mudanças e pode ser consultada por todo mundo pelo nome. Vamos transformar os 4 arquivos em tabelas.

CREATE OR REPLACE TABLE ecommerce.raw.vendas AS
SELECT
  id_venda,
  data_venda,
  id_cliente,
  id_produto,
  canal_venda,
  quantidade,
  CAST(preco_unitario AS DECIMAL(10, 2)) AS preco_unitario
FROM read_files('/Volumes/ecommerce/raw/arquivos/vendas.csv', format => 'csv', header => true);

CREATE OR REPLACE TABLE ecommerce.raw.produtos AS
SELECT
  id_produto,
  nome_produto,
  categoria,
  marca,
  CAST(preco_atual AS DECIMAL(10, 2)) AS preco_atual,
  data_criacao
FROM read_files('/Volumes/ecommerce/raw/arquivos/produtos.csv', format => 'csv', header => true);

CREATE OR REPLACE TABLE ecommerce.raw.clientes AS
SELECT
  id_cliente,
  nome_cliente,
  estado,
  pais,
  data_cadastro
FROM read_files('/Volumes/ecommerce/raw/arquivos/clientes.csv', format => 'csv', header => true);

CREATE OR REPLACE TABLE ecommerce.raw.preco_competidores AS
SELECT
  id_produto,
  nome_concorrente,
  CAST(preco_concorrente AS DECIMAL(10, 2)) AS preco_concorrente,
  data_coleta
FROM read_files('/Volumes/ecommerce/raw/arquivos/preco_competidores.csv', format => 'csv', header => true);

-- Veja o contrato da tabela `vendas`: cada coluna tem um tipo definido.

DESCRIBE TABLE ecommerce.raw.vendas;

-- ### A tabela se protege
-- Agora tente inserir uma venda com a quantidade escrita por extenso. **Esta célula vai dar erro, e o erro é o objetivo.**

INSERT INTO ecommerce.raw.vendas
VALUES ('sal_teste', current_timestamp(), 'cus_teste', 'prd_teste', 'ecommerce', 'duas', 99.90);

-- O Databricks recusou o valor `'duas'` porque a coluna `quantidade` é `INT`. Em um CSV esse erro passaria em silêncio e quebraria o relatório de alguém no mês seguinte.
-- ### A tabela lembra do passado
-- Toda alteração em uma tabela Delta vira uma **versão**. Vamos fazer uma alteração válida e olhar o histórico.

UPDATE ecommerce.raw.vendas
SET canal_venda = 'ECOMMERCE'
WHERE canal_venda = 'ecommerce';

DESCRIBE HISTORY ecommerce.raw.vendas;

-- Ops, padronizamos o canal errado. Dá para consultar a versão anterior (**time travel**) e voltar a tabela para ela:

SELECT canal_venda, COUNT(*) AS vendas
FROM ecommerce.raw.vendas VERSION AS OF 0
GROUP BY canal_venda;

RESTORE TABLE ecommerce.raw.vendas TO VERSION AS OF 0;

SELECT canal_venda, COUNT(*) AS vendas
FROM ecommerce.raw.vendas
GROUP BY canal_venda;
