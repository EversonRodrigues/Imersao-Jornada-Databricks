-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Aula 4 · Preparar o dado para a IA
-- MAGIC ### "Todo mundo quer IA. Ninguém tem o dado organizado."
-- MAGIC
-- MAGIC O Genie lê o **nome** e o **comentário** de cada tabela e coluna para decidir qual SQL escrever. Uma coluna chamada `receita` sem comentário obriga o Genie a adivinhar: é bruta ou líquida? Inclui frete? Em reais?
-- MAGIC
-- MAGIC Na Aula 3 os comentários foram escritos **junto com a definição** de cada tabela gold, no pipeline:
-- MAGIC
-- MAGIC ```sql
-- MAGIC CREATE OR REFRESH MATERIALIZED VIEW gold.vendas_temporais (
-- MAGIC   receita DECIMAL(20,2) COMMENT 'Receita bruta em reais (R$) = quantidade × preço unitário. Somar para totalizar.',
-- MAGIC   ...
-- MAGIC )
-- MAGIC COMMENT 'Vendas agregadas por dia, hora e canal. ...'
-- MAGIC AS SELECT ...
-- MAGIC ```
-- MAGIC
-- MAGIC Por estarem na definição, sobrevivem a cada atualização diária. Este notebook confere o que o Genie vai enxergar.

-- COMMAND ----------

-- MAGIC %python
-- MAGIC dbutils.widgets.text("catalogo", "ecommerce")

-- COMMAND ----------

USE CATALOG IDENTIFIER(:catalogo);

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## O que o Genie lê de cada tabela
-- MAGIC
-- MAGIC O comentário da tabela diz **quando usar** a tabela. É com ele que o Genie escolhe entre `vendas_temporais` (tempo e canal), `vendas_produtos` (produto), `clientes_segmentacao` (cliente), `precos_competitividade` (preço), `vendas_detalhadas` (perguntas que cruzam tudo) e `qualidade_dados` (confiabilidade).

-- COMMAND ----------

SELECT table_name AS tabela, comment AS comentario
FROM information_schema.tables
WHERE table_schema = 'gold'
  AND NOT startswith(table_name, '__materialization')  -- tabelas internas do pipeline
ORDER BY table_name;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## O que o Genie lê de cada coluna
-- MAGIC
-- MAGIC Repare nos detalhes que evitam resposta errada: `clientes_unicos` avisa que **não pode ser somado** entre linhas; `nome_produto` avisa que há **nomes repetidos**; `diferenca_pct_vs_media` diz que está em **pontos percentuais**.

-- COMMAND ----------

DESCRIBE TABLE gold.vendas_temporais;

-- COMMAND ----------

DESCRIBE TABLE gold.clientes_segmentacao;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Alguma coluna sem comentário?
-- MAGIC
-- MAGIC Zero linhas é o esperado. O teste `gold: toda coluna tem comentário`, na Aula 3, faz o Job falhar se alguém criar uma coluna nova sem explicar o que ela é.

-- COMMAND ----------

SELECT table_name AS tabela, column_name AS coluna
FROM information_schema.columns
WHERE table_schema = 'gold'
  AND NOT startswith(table_name, '__materialization')
  AND (comment IS NULL OR trim(comment) = '')
ORDER BY table_name, ordinal_position;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Próximo passo:** criar o Genie space (veja o `README.md` desta pasta). As instruções, as perguntas de exemplo e o SQL de referência estão em `genie/diretoria_ecommerce.geniespace.json`.
