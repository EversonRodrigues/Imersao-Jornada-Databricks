-- ============================================
-- Aula 1 · Diretoria de Vendas
-- Mesmas consultas do notebook 01_sql_e_dashboard.sql
-- ============================================

-- # 2. Diretoria de Vendas
-- > "Quanto vendemos no mês? Qual canal vende mais? Quais produtos e categorias puxam a receita?"
-- Antes de responder, precisamos **ver** os dados.
-- ### `SELECT` + `LIMIT`: o que tem aqui?

SELECT *
FROM ecommerce.raw.vendas
LIMIT 10;

-- ### `ORDER BY`: quais são as maiores vendas?
-- A receita de uma venda é `quantidade × preco_unitario`. Dá para calcular essa coluna na hora e dar um nome a ela com `AS`.

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

-- ### `WHERE`: só a loja física
-- `WHERE` filtra as linhas antes de qualquer cálculo. Combine condições com `AND` e `OR`.

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

-- ### Agregações: quanto vendemos?
-- `SUM`, `COUNT`, `AVG`, `MIN` e `MAX` resumem muitas linhas em **um** número. Esta é a primeira resposta para o Diretor Comercial.

SELECT
  COUNT(*)                                    AS total_vendas,
  COUNT(DISTINCT id_cliente)                  AS clientes_unicos,
  SUM(quantidade)                             AS itens_vendidos,
  ROUND(SUM(quantidade * preco_unitario), 2)  AS receita_total,
  ROUND(AVG(quantidade * preco_unitario), 2)  AS ticket_medio,
  MIN(data_venda)                             AS primeira_venda,
  MAX(data_venda)                             AS ultima_venda
FROM ecommerce.raw.vendas;

-- ### `GROUP BY`: e por canal?
-- `GROUP BY` faz a mesma conta **separada por grupo**.
-- **Regra de ouro:** toda coluna do `SELECT` precisa estar no `GROUP BY` ou dentro de uma agregação.

SELECT
  canal_venda,
  COUNT(*)                                   AS total_vendas,
  ROUND(SUM(quantidade * preco_unitario), 2) AS receita_total,
  ROUND(AVG(quantidade * preco_unitario), 2) AS ticket_medio
FROM ecommerce.raw.vendas
GROUP BY canal_venda
ORDER BY receita_total DESC;

-- Receita por dia. `DATE()` corta o horário e deixa só a data. Clique em **+ → Visualization** no resultado para ver como gráfico de linha.

SELECT
  DATE(data_venda)                           AS dia,
  COUNT(*)                                   AS total_vendas,
  ROUND(SUM(quantidade * preco_unitario), 2) AS receita_total
FROM ecommerce.raw.vendas
GROUP BY DATE(data_venda)
ORDER BY dia;

-- ### `JOIN`: qual categoria vende mais?
-- A tabela `vendas` só tem o `id_produto`. O nome e a categoria estão em `produtos`. O `JOIN` usa a coluna em comum como ponte:
-- vendas.id_produto  ──JOIN──  produtos.id_produto

SELECT
  p.categoria,
  COUNT(*)                                       AS total_vendas,
  ROUND(SUM(v.quantidade * v.preco_unitario), 2) AS receita_total
FROM ecommerce.raw.vendas v
JOIN ecommerce.raw.produtos p
  ON v.id_produto = p.id_produto
GROUP BY p.categoria
ORDER BY receita_total DESC;

-- **Top 10 produtos por receita.** É a resposta que o Diretor Comercial leva para a reunião de estoque.

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

-- ### Pegadinha: o `JOIN` sumiu com vendas
-- Compare a receita total com e sem o `JOIN`. Os números não batem.

SELECT 'sem JOIN' AS consulta, ROUND(SUM(quantidade * preco_unitario), 2) AS receita
FROM ecommerce.raw.vendas
UNION ALL
SELECT 'com JOIN', ROUND(SUM(v.quantidade * v.preco_unitario), 2)
FROM ecommerce.raw.vendas v
JOIN ecommerce.raw.produtos p ON v.id_produto = p.id_produto;

-- Existem vendas de produtos que **não estão cadastrados**. O `JOIN` (que é um `INNER JOIN`) descarta essas linhas. O `LEFT JOIN` mantém todas as vendas e deixa `NULL` onde não achou o produto:

SELECT
  v.id_produto,
  COUNT(*)                                       AS vendas,
  ROUND(SUM(v.quantidade * v.preco_unitario), 2) AS receita
FROM ecommerce.raw.vendas v
LEFT JOIN ecommerce.raw.produtos p
  ON v.id_produto = p.id_produto
WHERE p.id_produto IS NULL
GROUP BY v.id_produto;
