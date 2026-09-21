-- ============================================
-- Aula 1 · Bônus: CASE WHEN e window functions
-- Mesmas consultas do notebook 01_sql_e_dashboard.sql
-- ============================================

-- # Bônus (para praticar em casa)
-- ### `CASE WHEN`: classificar é o "se / então / senão" do SQL
-- Segmentação de clientes pela receita total. Esta é a mesma regra usada na camada gold da Aula 2.

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

-- ### Window functions: comparar sem perder o detalhe
-- `GROUP BY` junta as linhas. Uma window function **mantém** as linhas e adiciona um cálculo que olha para as outras.
-- - `ROW_NUMBER()`: ranking
-- - `PARTITION BY`: ranking que recomeça em cada grupo
-- - `SUM() OVER ()`: total geral, útil para percentuais
-- - `LAG()`: valor da linha anterior

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

-- Percentual da receita por canal
SELECT
  canal_venda,
  ROUND(SUM(quantidade * preco_unitario), 2) AS receita_total,
  ROUND(SUM(quantidade * preco_unitario) * 100 / SUM(SUM(quantidade * preco_unitario)) OVER (), 1) AS pct_receita
FROM ecommerce.raw.vendas
GROUP BY canal_venda;

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
