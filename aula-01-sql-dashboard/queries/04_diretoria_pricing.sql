-- ============================================
-- Aula 1 · Diretoria de Pricing
-- Mesmas consultas do notebook 01_sql_e_dashboard.sql
-- ============================================

-- # 4. Diretoria de Pricing
-- > "Estamos mais caros que a concorrência?"
-- Cada produto tem até 4 preços de concorrentes (Mercado Livre, Amazon, Magalu e Shopee). Primeiro, uma olhada:

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

-- ### Competitividade por produto
-- Para cada produto: nosso preço, a média, o menor e o maior preço dos concorrentes, e a diferença percentual contra a média.
-- `diferenca_pct_vs_media` positiva significa que **estamos mais caros**.

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

-- ### Quais produtos estão mais caros que **todos** os concorrentes?
-- `WHERE` filtra linhas **antes** do agrupamento. Para filtrar **depois** (usando o resultado de uma agregação) usamos `HAVING`.

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

-- **Competitividade por categoria.** Onde o problema se concentra?

SELECT
  p.categoria,
  COUNT(DISTINCT p.id_produto)                                                         AS produtos,
  ROUND(AVG((p.preco_atual - pc.preco_concorrente) / pc.preco_concorrente * 100), 1)   AS diferenca_pct_media
FROM ecommerce.raw.produtos p
JOIN ecommerce.raw.preco_competidores pc
  ON p.id_produto = pc.id_produto
GROUP BY p.categoria
ORDER BY diferenca_pct_media DESC;

-- A categoria **Tênis** está muito acima do mercado. O Diretor de Pricing agora tem por onde começar.
-- # 5. Dashboard: uma página por diretoria
-- As respostas já existem. Falta colocá-las onde os diretores enxergam sem abrir um notebook.
-- **Opção A: importar o dashboard pronto (2 min)**
-- 1. Baixe `aula-01-sql-dashboard/dashboard/diretoria_ecommerce.lvdash.json` do repositório.
-- 2. Menu lateral **Dashboards → seta ao lado de Create dashboard → Import dashboard from file**.
-- 3. Selecione o arquivo e clique em **Publish**.
-- **Opção B: montar do zero (15 min, recomendado na aula ao vivo)**
-- 1. **Dashboards → Create dashboard**. Renomeie para *Diretoria E-commerce*.
-- 2. Aba **Data → Create from SQL**: cole as queries dos blocos 2, 3 e 4 (uma por dataset). O passo a passo completo está no `README.md` desta pasta.
-- 3. Aba do canvas: crie **3 páginas** (Vendas, Clientes e Pricing) e adicione os gráficos.
-- 4. **Publish** e compartilhe o link.
-- > Na Aula 4, os diretores deixam de precisar do painel para perguntar: eles vão conversar com os dados pelo **Genie**.
