-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Aula 1: SQL & Dashboard
-- MAGIC ### Imersão Jornada de Dados no Databricks
-- MAGIC
-- MAGIC Uma empresa de e-commerce acabou de abrir a operação digital. Três diretores têm perguntas **hoje**, e ninguém ainda olhou para os dados.
-- MAGIC
-- MAGIC Neste notebook você vai responder cada um deles com SQL e, no fim, montar um **dashboard** com uma página por diretoria.
-- MAGIC
-- MAGIC | Bloco | Tempo | O que acontece |
-- MAGIC |---|---|---|
-- MAGIC | 0. Setup | antes da aula | Catálogo, schemas, volume e as 4 tabelas |
-- MAGIC | 1. CSV × Tabela | 5 min | Por que dado em tabela é diferente de dado em arquivo |
-- MAGIC | 2. Diretoria de Vendas | 25 min | `SELECT`, `LIMIT`, `ORDER BY`, `WHERE`, agregações, `GROUP BY`, `JOIN` |
-- MAGIC | 3. Diretoria de Clientes | 15 min | Top 10 clientes, clientes por estado |
-- MAGIC | 4. Diretoria de Pricing | 15 min | Nosso preço × preço dos concorrentes |
-- MAGIC | 5. Dashboard | 15 min | Uma página por diretoria |
-- MAGIC | Bônus | casa | `CASE WHEN` e window functions |
-- MAGIC
-- MAGIC > **Como rodar:** conecte o notebook em **Serverless** (canto superior direito) e execute célula por célula com `Shift + Enter`.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Os três diretores
-- MAGIC
-- MAGIC **Diretor Comercial (Vendas)**
-- MAGIC > "Quanto vendemos no mês? Qual canal vende mais, o e-commerce ou a loja física? Quais produtos e categorias puxam a receita?"
-- MAGIC
-- MAGIC **Diretora de Customer Success (Clientes)**
-- MAGIC > "Quem são nossos 10 melhores clientes? De quais estados eles são? Preciso planejar a equipe regional."
-- MAGIC
-- MAGIC **Diretor de Pricing (Preços)**
-- MAGIC > "Estamos mais caros que a concorrência? Quais produtos estão mais caros que **todos** os concorrentes?"
-- MAGIC
-- MAGIC Hoje essas perguntas levam dias para serem respondidas. No fim desta aula elas estarão em um painel.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ---
-- MAGIC # 0. Setup
-- MAGIC
-- MAGIC No Databricks os dados são organizados em três níveis, pelo **Unity Catalog**:
-- MAGIC
-- MAGIC ```
-- MAGIC catálogo  →  schema  →  tabela / volume
-- MAGIC ecommerce →  raw     →  vendas, produtos, clientes, preco_competidores
-- MAGIC                      →  arquivos (volume: onde ficam os CSVs)
-- MAGIC ```
-- MAGIC
-- MAGIC Vamos criar também os schemas `bronze`, `silver` e `gold`, que serão usados a partir da Aula 2.

-- COMMAND ----------

CREATE CATALOG IF NOT EXISTS ecommerce COMMENT 'Imersão Jornada de Dados: e-commerce';

CREATE SCHEMA IF NOT EXISTS ecommerce.raw    COMMENT 'Dados como chegaram da origem';
CREATE SCHEMA IF NOT EXISTS ecommerce.bronze COMMENT 'Aula 2: ingestão com metadados';
CREATE SCHEMA IF NOT EXISTS ecommerce.silver COMMENT 'Aula 2: dados limpos e padronizados';
CREATE SCHEMA IF NOT EXISTS ecommerce.gold   COMMENT 'Aula 2: tabelas prontas para o negócio';

CREATE VOLUME IF NOT EXISTS ecommerce.raw.arquivos COMMENT 'Arquivos brutos (CSV, Parquet, JSON)';

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Enviar os 4 CSVs para o volume
-- MAGIC
-- MAGIC 1. Baixe os arquivos da pasta `dados/` do repositório: `produtos.csv`, `clientes.csv`, `vendas.csv` e `preco_competidores.csv`.
-- MAGIC 2. No menu lateral, abra **Catalog → ecommerce → raw → arquivos**.
-- MAGIC 3. Clique em **Upload to this volume** e arraste os 4 arquivos.
-- MAGIC
-- MAGIC Confira se eles chegaram:

-- COMMAND ----------

LIST '/Volumes/ecommerce/raw/arquivos/';

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ---
-- MAGIC # 1. CSV × Tabela
-- MAGIC
-- MAGIC Dá para consultar o arquivo direto com `read_files`. O Databricks lê o CSV e **adivinha** os tipos de cada coluna.

-- COMMAND ----------

SELECT *
FROM read_files(
  '/Volumes/ecommerce/raw/arquivos/vendas.csv',
  format => 'csv',
  header => true
)
LIMIT 10;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Consultar o arquivo funciona, mas um arquivo não garante nada: qualquer um pode abrir o CSV e escrever "duas" na coluna de quantidade.
-- MAGIC
-- MAGIC Uma **tabela Delta** tem um contrato (schema), guarda o histórico de mudanças e pode ser consultada por todo mundo pelo nome. Vamos transformar os 4 arquivos em tabelas.

-- COMMAND ----------

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

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Veja o contrato da tabela `vendas`: cada coluna tem um tipo definido.

-- COMMAND ----------

DESCRIBE TABLE ecommerce.raw.vendas;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### A tabela se protege
-- MAGIC
-- MAGIC Agora tente inserir uma venda com a quantidade escrita por extenso. **Esta célula vai dar erro, e o erro é o objetivo.**

-- COMMAND ----------

INSERT INTO ecommerce.raw.vendas
VALUES ('sal_teste', current_timestamp(), 'cus_teste', 'prd_teste', 'ecommerce', 'duas', 99.90);

-- COMMAND ----------

-- MAGIC %md
-- MAGIC O Databricks recusou o valor `'duas'` porque a coluna `quantidade` é `INT`. Em um CSV esse erro passaria em silêncio e quebraria o relatório de alguém no mês seguinte.
-- MAGIC
-- MAGIC ### A tabela lembra do passado
-- MAGIC
-- MAGIC Toda alteração em uma tabela Delta vira uma **versão**. Vamos fazer uma alteração válida e olhar o histórico.

-- COMMAND ----------

UPDATE ecommerce.raw.vendas
SET canal_venda = 'ECOMMERCE'
WHERE canal_venda = 'ecommerce';

-- COMMAND ----------

DESCRIBE HISTORY ecommerce.raw.vendas;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Ops, padronizamos o canal errado. Dá para consultar a versão anterior (**time travel**) e voltar a tabela para ela:

-- COMMAND ----------

SELECT canal_venda, COUNT(*) AS vendas
FROM ecommerce.raw.vendas VERSION AS OF 0
GROUP BY canal_venda;

-- COMMAND ----------

RESTORE TABLE ecommerce.raw.vendas TO VERSION AS OF 0;

-- COMMAND ----------

SELECT canal_venda, COUNT(*) AS vendas
FROM ecommerce.raw.vendas
GROUP BY canal_venda;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ---
-- MAGIC # 2. Diretoria de Vendas
-- MAGIC
-- MAGIC > "Quanto vendemos no mês? Qual canal vende mais? Quais produtos e categorias puxam a receita?"
-- MAGIC
-- MAGIC Antes de responder, precisamos **ver** os dados.
-- MAGIC
-- MAGIC ### `SELECT` + `LIMIT`: o que tem aqui?

-- COMMAND ----------

SELECT *
FROM ecommerce.raw.vendas
LIMIT 10;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### `ORDER BY`: quais são as maiores vendas?
-- MAGIC
-- MAGIC A receita de uma venda é `quantidade × preco_unitario`. Dá para calcular essa coluna na hora e dar um nome a ela com `AS`.

-- COMMAND ----------

SELECT
  id_venda,
  data_venda,
  canal_venda,
  quantidade,
  preco_unitario,
  quantidade * preco_unitario AS receita
FROM ecommerce.raw.vendas
ORDER BY receita DESC
LIMIT 10;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### `WHERE`: só a loja física
-- MAGIC
-- MAGIC `WHERE` filtra as linhas antes de qualquer cálculo. Combine condições com `AND` e `OR`.

-- COMMAND ----------

SELECT
  id_venda,
  data_venda,
  quantidade,
  preco_unitario
FROM ecommerce.raw.vendas
WHERE canal_venda = 'loja_fisica'
  AND quantidade > 1
ORDER BY preco_unitario DESC
LIMIT 10;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Agregações: quanto vendemos?
-- MAGIC
-- MAGIC `SUM`, `COUNT`, `AVG`, `MIN` e `MAX` resumem muitas linhas em **um** número. Esta é a primeira resposta para o Diretor Comercial.

-- COMMAND ----------

SELECT
  COUNT(*)                                    AS total_vendas,
  COUNT(DISTINCT id_cliente)                  AS clientes_unicos,
  SUM(quantidade)                             AS itens_vendidos,
  ROUND(SUM(quantidade * preco_unitario), 2)  AS receita_total,
  ROUND(AVG(quantidade * preco_unitario), 2)  AS ticket_medio,
  MIN(data_venda)                             AS primeira_venda,
  MAX(data_venda)                             AS ultima_venda
FROM ecommerce.raw.vendas;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### `GROUP BY`: e por canal?
-- MAGIC
-- MAGIC `GROUP BY` faz a mesma conta **separada por grupo**.
-- MAGIC
-- MAGIC **Regra de ouro:** toda coluna do `SELECT` precisa estar no `GROUP BY` ou dentro de uma agregação.

-- COMMAND ----------

SELECT
  canal_venda,
  COUNT(*)                                   AS total_vendas,
  ROUND(SUM(quantidade * preco_unitario), 2) AS receita_total,
  ROUND(AVG(quantidade * preco_unitario), 2) AS ticket_medio
FROM ecommerce.raw.vendas
GROUP BY canal_venda
ORDER BY receita_total DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Receita por dia. `DATE()` corta o horário e deixa só a data. Clique em **+ → Visualization** no resultado para ver como gráfico de linha.

-- COMMAND ----------

SELECT
  DATE(data_venda)                           AS dia,
  COUNT(*)                                   AS total_vendas,
  ROUND(SUM(quantidade * preco_unitario), 2) AS receita_total
FROM ecommerce.raw.vendas
GROUP BY DATE(data_venda)
ORDER BY dia;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### `JOIN`: qual categoria vende mais?
-- MAGIC
-- MAGIC A tabela `vendas` só tem o `id_produto`. O nome e a categoria estão em `produtos`. O `JOIN` usa a coluna em comum como ponte:
-- MAGIC
-- MAGIC ```
-- MAGIC vendas.id_produto  ──JOIN──  produtos.id_produto
-- MAGIC ```

-- COMMAND ----------

SELECT
  p.categoria,
  COUNT(*)                                       AS total_vendas,
  ROUND(SUM(v.quantidade * v.preco_unitario), 2) AS receita_total
FROM ecommerce.raw.vendas v
JOIN ecommerce.raw.produtos p
  ON v.id_produto = p.id_produto
GROUP BY p.categoria
ORDER BY receita_total DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Top 10 produtos por receita.** É a resposta que o Diretor Comercial leva para a reunião de estoque.

-- COMMAND ----------

SELECT
  p.nome_produto,
  p.categoria,
  p.marca,
  SUM(v.quantidade)                              AS itens_vendidos,
  ROUND(SUM(v.quantidade * v.preco_unitario), 2) AS receita_total
FROM ecommerce.raw.vendas v
JOIN ecommerce.raw.produtos p
  ON v.id_produto = p.id_produto
GROUP BY p.nome_produto, p.categoria, p.marca
ORDER BY receita_total DESC
LIMIT 10;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Pegadinha: o `JOIN` sumiu com vendas
-- MAGIC
-- MAGIC Compare a receita total com e sem o `JOIN`. Os números não batem.

-- COMMAND ----------

SELECT 'sem JOIN' AS consulta, ROUND(SUM(quantidade * preco_unitario), 2) AS receita
FROM ecommerce.raw.vendas
UNION ALL
SELECT 'com JOIN', ROUND(SUM(v.quantidade * v.preco_unitario), 2)
FROM ecommerce.raw.vendas v
JOIN ecommerce.raw.produtos p ON v.id_produto = p.id_produto;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Existem vendas de produtos que **não estão cadastrados**. O `JOIN` (que é um `INNER JOIN`) descarta essas linhas. O `LEFT JOIN` mantém todas as vendas e deixa `NULL` onde não achou o produto:

-- COMMAND ----------

SELECT
  v.id_produto,
  COUNT(*)                                       AS vendas,
  ROUND(SUM(v.quantidade * v.preco_unitario), 2) AS receita
FROM ecommerce.raw.vendas v
LEFT JOIN ecommerce.raw.produtos p
  ON v.id_produto = p.id_produto
WHERE p.id_produto IS NULL
GROUP BY v.id_produto;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC Esse é um problema de **qualidade de dados**, e ele volta na Aula 2 (camada silver) e na Aula 3 (testes automáticos).
-- MAGIC
-- MAGIC ---
-- MAGIC # 3. Diretoria de Clientes
-- MAGIC
-- MAGIC > "Quem são nossos 10 melhores clientes? De quais estados eles são?"

-- COMMAND ----------

SELECT
  c.nome_cliente,
  c.estado,
  COUNT(*)                                       AS total_compras,
  ROUND(SUM(v.quantidade * v.preco_unitario), 2) AS receita_total,
  ROUND(AVG(v.quantidade * v.preco_unitario), 2) AS ticket_medio
FROM ecommerce.raw.vendas v
JOIN ecommerce.raw.clientes c
  ON v.id_cliente = c.id_cliente
GROUP BY c.nome_cliente, c.estado
ORDER BY receita_total DESC
LIMIT 10;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Clientes e receita por estado**, para planejar a equipe regional.

-- COMMAND ----------

SELECT
  c.estado,
  COUNT(DISTINCT c.id_cliente)                   AS clientes,
  ROUND(SUM(v.quantidade * v.preco_unitario), 2) AS receita_total
FROM ecommerce.raw.vendas v
JOIN ecommerce.raw.clientes c
  ON v.id_cliente = c.id_cliente
GROUP BY c.estado
ORDER BY receita_total DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ---
-- MAGIC # 4. Diretoria de Pricing
-- MAGIC
-- MAGIC > "Estamos mais caros que a concorrência?"
-- MAGIC
-- MAGIC Cada produto tem até 4 preços de concorrentes (Mercado Livre, Amazon, Magalu e Shopee). Primeiro, uma olhada:

-- COMMAND ----------

SELECT
  p.nome_produto,
  p.preco_atual     AS nosso_preco,
  pc.nome_concorrente,
  pc.preco_concorrente
FROM ecommerce.raw.produtos p
JOIN ecommerce.raw.preco_competidores pc
  ON p.id_produto = pc.id_produto
ORDER BY p.nome_produto, pc.preco_concorrente
LIMIT 20;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Competitividade por produto
-- MAGIC
-- MAGIC Para cada produto: nosso preço, a média, o menor e o maior preço dos concorrentes, e a diferença percentual contra a média.
-- MAGIC
-- MAGIC `diferenca_pct_vs_media` positiva significa que **estamos mais caros**.

-- COMMAND ----------

SELECT
  p.nome_produto,
  p.categoria,
  p.preco_atual                                                              AS nosso_preco,
  ROUND(AVG(pc.preco_concorrente), 2)                                        AS preco_medio_concorrentes,
  MIN(pc.preco_concorrente)                                                  AS menor_preco_concorrente,
  MAX(pc.preco_concorrente)                                                  AS maior_preco_concorrente,
  ROUND((p.preco_atual - AVG(pc.preco_concorrente)) / AVG(pc.preco_concorrente) * 100, 1) AS diferenca_pct_vs_media
FROM ecommerce.raw.produtos p
JOIN ecommerce.raw.preco_competidores pc
  ON p.id_produto = pc.id_produto
GROUP BY p.nome_produto, p.categoria, p.preco_atual
ORDER BY diferenca_pct_vs_media DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Quais produtos estão mais caros que **todos** os concorrentes?
-- MAGIC
-- MAGIC `WHERE` filtra linhas **antes** do agrupamento. Para filtrar **depois** (usando o resultado de uma agregação) usamos `HAVING`.

-- COMMAND ----------

SELECT
  p.nome_produto,
  p.categoria,
  p.preco_atual                  AS nosso_preco,
  MAX(pc.preco_concorrente)      AS maior_preco_concorrente,
  COUNT(pc.nome_concorrente)     AS concorrentes_monitorados
FROM ecommerce.raw.produtos p
JOIN ecommerce.raw.preco_competidores pc
  ON p.id_produto = pc.id_produto
GROUP BY p.nome_produto, p.categoria, p.preco_atual
HAVING p.preco_atual > MAX(pc.preco_concorrente)
ORDER BY p.categoria, nosso_preco DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Competitividade por categoria.** Onde o problema se concentra?

-- COMMAND ----------

SELECT
  p.categoria,
  COUNT(DISTINCT p.id_produto)                                                         AS produtos,
  ROUND(AVG((p.preco_atual - pc.preco_concorrente) / pc.preco_concorrente * 100), 1)   AS diferenca_pct_media
FROM ecommerce.raw.produtos p
JOIN ecommerce.raw.preco_competidores pc
  ON p.id_produto = pc.id_produto
GROUP BY p.categoria
ORDER BY diferenca_pct_media DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC A categoria **Tênis** está muito acima do mercado. O Diretor de Pricing agora tem por onde começar.
-- MAGIC
-- MAGIC ---
-- MAGIC # 5. Dashboard: uma página por diretoria
-- MAGIC
-- MAGIC As respostas já existem. Falta colocá-las onde os diretores enxergam sem abrir um notebook.
-- MAGIC
-- MAGIC **Opção A: importar o dashboard pronto (2 min)**
-- MAGIC 1. Baixe `aula-01-sql-dashboard/dashboard/diretoria_ecommerce.lvdash.json` do repositório.
-- MAGIC 2. Menu lateral **Dashboards → seta ao lado de Create dashboard → Import dashboard from file**.
-- MAGIC 3. Selecione o arquivo e clique em **Publish**.
-- MAGIC
-- MAGIC **Opção B: montar do zero (15 min, recomendado na aula ao vivo)**
-- MAGIC 1. **Dashboards → Create dashboard**. Renomeie para *Diretoria E-commerce*.
-- MAGIC 2. Aba **Data → Create from SQL**: cole as queries dos blocos 2, 3 e 4 (uma por dataset). O passo a passo completo está no `README.md` desta pasta.
-- MAGIC 3. Aba do canvas: crie **3 páginas** (Vendas, Clientes e Pricing) e adicione os gráficos.
-- MAGIC 4. **Publish** e compartilhe o link.
-- MAGIC
-- MAGIC > Na Aula 4, os diretores deixam de precisar do painel para perguntar: eles vão conversar com os dados pelo **Genie**.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ---
-- MAGIC # Bônus (para praticar em casa)
-- MAGIC
-- MAGIC ### `CASE WHEN`: classificar é o "se / então / senão" do SQL
-- MAGIC
-- MAGIC Segmentação de clientes pela receita total. Esta é a mesma regra usada na camada gold da Aula 2.

-- COMMAND ----------

SELECT
  c.nome_cliente,
  ROUND(SUM(v.quantidade * v.preco_unitario), 2) AS receita_total,
  CASE
    WHEN SUM(v.quantidade * v.preco_unitario) >= 22000 THEN 'VIP'
    WHEN SUM(v.quantidade * v.preco_unitario) >= 17000 THEN 'TOP_TIER'
    ELSE 'REGULAR'
  END AS segmento
FROM ecommerce.raw.vendas v
JOIN ecommerce.raw.clientes c
  ON v.id_cliente = c.id_cliente
GROUP BY c.nome_cliente
ORDER BY receita_total DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Window functions: comparar sem perder o detalhe
-- MAGIC
-- MAGIC `GROUP BY` junta as linhas. Uma window function **mantém** as linhas e adiciona um cálculo que olha para as outras.
-- MAGIC
-- MAGIC - `ROW_NUMBER()`: ranking
-- MAGIC - `PARTITION BY`: ranking que recomeça em cada grupo
-- MAGIC - `SUM() OVER ()`: total geral, útil para percentuais
-- MAGIC - `LAG()`: valor da linha anterior

-- COMMAND ----------

-- Top 3 produtos de cada categoria
SELECT *
FROM (
  SELECT
    p.categoria,
    p.nome_produto,
    ROUND(SUM(v.quantidade * v.preco_unitario), 2) AS receita_total,
    ROW_NUMBER() OVER (
      PARTITION BY p.categoria
      ORDER BY SUM(v.quantidade * v.preco_unitario) DESC
    ) AS ranking_na_categoria
  FROM ecommerce.raw.vendas v
  JOIN ecommerce.raw.produtos p
    ON v.id_produto = p.id_produto
  GROUP BY p.categoria, p.nome_produto
)
WHERE ranking_na_categoria <= 3
ORDER BY categoria, ranking_na_categoria;

-- COMMAND ----------

-- Percentual da receita por canal
SELECT
  canal_venda,
  ROUND(SUM(quantidade * preco_unitario), 2) AS receita_total,
  ROUND(SUM(quantidade * preco_unitario) * 100 / SUM(SUM(quantidade * preco_unitario)) OVER (), 1) AS pct_receita
FROM ecommerce.raw.vendas
GROUP BY canal_venda;

-- COMMAND ----------

-- Receita de cada dia comparada com o dia anterior
SELECT
  dia,
  receita_total,
  LAG(receita_total) OVER (ORDER BY dia)                                              AS receita_dia_anterior,
  ROUND((receita_total - LAG(receita_total) OVER (ORDER BY dia)) * 100
        / LAG(receita_total) OVER (ORDER BY dia), 1)                                  AS variacao_pct
FROM (
  SELECT DATE(data_venda) AS dia, ROUND(SUM(quantidade * preco_unitario), 2) AS receita_total
  FROM ecommerce.raw.vendas
  GROUP BY DATE(data_venda)
)
ORDER BY dia;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ---
-- MAGIC ## Recap do Dia 1
-- MAGIC
-- MAGIC - Você criou um catálogo, schemas, um volume e 4 tabelas Delta.
-- MAGIC - Viu que uma tabela recusa dado errado e guarda o histórico (`DESCRIBE HISTORY`, `RESTORE`).
-- MAGIC - Respondeu os 3 diretores com `SELECT`, `WHERE`, `GROUP BY`, `HAVING` e `JOIN`.
-- MAGIC - Encontrou um problema real de qualidade: vendas de produtos não cadastrados.
-- MAGIC - Publicou um dashboard com uma página por diretoria.
-- MAGIC
-- MAGIC **Amanhã:** você subiu os CSVs na mão. E quando chegar um arquivo novo todo dia? Na Aula 2 vamos **automatizar a chegada do dado**.
