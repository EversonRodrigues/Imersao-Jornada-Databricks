# Prompt 3: Diretoria de Customer Success

Agora a gold da Diretoria de Customer Success. A diretora quer saber quem são os melhores clientes,
onde estão (estado e região) e como dividir a carteira em segmentos. Siga as regras de gold do
CLAUDE.md: SQL, CREATE OR REFRESH MATERIALIZED VIEW, tipo e COMMENT em todas as colunas, COMMENT
na tabela, em português.

TABELA
gold.clientes_segmentacao, uma linha por cliente, INCLUSIVE quem nunca comprou (LEFT JOIN a partir de
silver.clientes, receita zero). É justamente esse cliente que o time de CS precisa ativar.
Colunas: id_cliente, nome_cliente (sem pronome de tratamento), estado, nome_estado, regiao,
total_compras, receita (COALESCE 0), ticket_medio (ROUND(AVG(receita), 2)), primeira_compra,
ultima_compra, segmento_cliente, ranking_receita (ROW_NUMBER por receita desc).

REGRA DE SEGMENTAÇÃO (definida com a diretora, a partir da distribuição real)
- VIP: receita a partir de R$ 22.000
- TOP_TIER: de R$ 17.000 até R$ 21.999,99
- REGULAR: abaixo de R$ 17.000
Explique no comentário do arquivo por que os limites antigos (R$ 10.000 e R$ 5.000) não serviam:
com eles quase todo mundo virava VIP.

Se gold.vendas_detalhadas já existe, confira se ela usa esta tabela para o segmento.

TESTES (no notebook de testes que já existe)
- receita total igual à de silver.vendas;
- id_cliente único; segmento só VIP, TOP_TIER ou REGULAR; nenhum VIP com receita abaixo de 22.000;
- toda venda de vendas_detalhadas com segmento e região.

NO FIM
Valide, faça o deploy em dev, rode o Job e confira: 50 clientes; 10 VIP, 25 TOP_TIER e 15 REGULAR;
receita R$ 974.077,28; o maior cliente é Ana Sophia Pereira (MG, R$ 30.716,63).
