-- ============================================
-- Aula 1 · Diretoria de Clientes
-- Mesmas consultas do notebook 01_sql_e_dashboard.sql
-- ============================================

-- # 3. Diretoria de Clientes
-- > "Quem são nossos 10 melhores clientes? De quais estados eles são?"

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

-- **Clientes e receita por estado**, para planejar a equipe regional.

SELECT
  c.estado,
  COUNT(DISTINCT c.id_cliente)                   AS clientes,
  ROUND(SUM(v.quantidade * v.preco_unitario), 2) AS receita_total
FROM ecommerce.raw.vendas v
JOIN ecommerce.raw.clientes c
  ON v.id_cliente = c.id_cliente
GROUP BY c.estado
ORDER BY receita_total DESC;
