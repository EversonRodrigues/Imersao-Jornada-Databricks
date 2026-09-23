# Prompt 2: Diretoria Comercial

Agora a gold da Diretoria Comercial. A diretora quer saber: quanto vendemos, quando (dia, hora,
dia da semana), em qual canal e com quais produtos. Ela vai usar um dashboard e o Genie (IA que
escreve SQL a partir de perguntas em português), então as tabelas precisam ser autoexplicativas.

REGRAS PARA TODA GOLD (grave no CLAUDE.md, valem para as próximas diretorias)
- SQL, um arquivo por tabela em transformations/gold/, CREATE OR REFRESH MATERIALIZED VIEW gold.<tabela>.
- Declare TODAS as colunas entre parênteses com tipo e COMMENT (sem o tipo, o comentário é ignorado),
  e COMMENT na tabela dizendo quando usar a tabela. Comentários em português, com unidade (R$),
  regra de cálculo e avisos que evitem erro do Genie.
- Inclua TODAS as vendas, inclusive de produto não cadastrado: dinheiro que entrou é receita.
- Período dos dados: 13/12/2025 a 11/01/2026. Cite isso no comentário das tabelas de vendas.

TABELAS
1. gold.vendas_temporais, uma linha por data × hora × canal_venda.
   Colunas: data, dia_semana, dia_semana_num, hora, canal_venda, total_vendas (COUNT), itens_vendidos
   (SUM quantidade), receita (SUM), clientes_unicos (COUNT DISTINCT id_cliente).
   Aviso no comentário de clientes_unicos: não somar entre linhas.
2. gold.vendas_produtos, uma linha por produto vendido (LEFT JOIN de silver.vendas com silver.produtos).
   Colunas: id_produto; nome_produto, categoria e marca (quando o produto não existe: "Produto não
   cadastrado" e "Não cadastrado"); faixa_preco; produto_cadastrado; total_vendas; itens_vendidos;
   receita; ticket_medio (ROUND(AVG(receita), 2)); ranking_receita (ROW_NUMBER geral por receita desc);
   ranking_na_categoria (ROW_NUMBER por categoria).
   Aviso no comentário de nome_produto: produtos diferentes têm o mesmo nome, contar por id_produto.
3. gold.vendas_detalhadas, uma linha por venda, para perguntas que cruzam diretorias e para os
   filtros cruzados do dashboard. Colunas: id_venda, data_venda, data, dia_semana, dia_semana_num, hora,
   canal_venda, id_produto, nome_produto, categoria, marca, faixa_preco (mesmos "não cadastrado" da
   anterior), id_cliente, nome_cliente, estado, regiao, segmento_cliente (de gold.clientes_segmentacao;
   se ela ainda não existir, avise que ela vem no próximo prompt e crie-a seguindo a regra VIP >= 22.000,
   TOP_TIER >= 17.000, REGULAR abaixo), quantidade, preco_unitario, receita, produto_cadastrado,
   venda_antes_do_cadastro. CLUSTER BY (data).

TESTES
Crie um notebook testes/testes_qualidade.py (formato source do Databricks, widget catalogo) com um
dicionário de consultas que contam linhas com problema e falha com AssertionError se alguma achar:
- receita total de cada gold desta diretoria igual à de silver.vendas;
- vendas_detalhadas com o mesmo número de linhas de silver.vendas e id_venda único;
- toda coluna do schema gold com comentário (ignorando tabelas que começam com __materialization);
- vendas de produto não cadastrado abaixo de 1% do total.
Adicione ao bundle um Job "Pipeline E-commerce" que roda o pipeline e depois esse notebook.

NO FIM
Valide, faça o deploy em dev, rode o Job e confira: receita R$ 974.077,28 e 3.020 vendas em
silver.vendas, vendas_temporais, vendas_produtos e vendas_detalhadas; 2.155 vendas no ecommerce.
