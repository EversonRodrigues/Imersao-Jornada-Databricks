# Prompt 1: a silver

Vamos construir a camada silver de um e-commerce brasileiro no Databricks, como um Lakeflow
Declarative Pipeline dentro deste bundle. Use sempre o perfil de CLI "imersao".

CONTEXTO
- Catálogo ecommerce. A bronze já existe e é sobrescrita todo dia por outra ingestão:
  bronze.vendas, bronze.produtos, bronze.clientes, bronze.preco_competidores (todos vindos de
  Parquet) e bronze.estados_ibge (API do IBGE, colunas sigla, nome, regiao_nome).
- Antes de escrever código, explore a bronze (colunas, tipos, contagens) e procure problemas de
  qualidade. Me mostre os números.

CONVENÇÕES (grave no CLAUDE.md)
- Nomes de tabelas e colunas em português, snake_case, sem acento.
- Silver em Python (from pyspark import pipelines as dp), gold em SQL.
- Um arquivo por tabela: transformations/silver/<tabela>.py e transformations/gold/<tabela>.sql.
  Apague os exemplos que vieram no template.
- Todas as tabelas são materialized views com leitura batch (spark.read.table), nunca streaming
  table, porque a bronze é sobrescrita a cada execução.
- Pipeline serverless, catálogo ecommerce, schema padrão silver. Golds publicadas como gold.<tabela>.
  Nomes no código sempre schema.tabela, sem catálogo. Crie os schemas silver e gold se não existirem.
- Cada arquivo começa com comentários explicando o PORQUÊ das regras, em português.
- Dinheiro sempre DECIMAL(10,2).
- Problema de qualidade conhecido é MARCADO em uma coluna e medido com @dp.expect (warn).
  Nunca descarte linhas: apagar vendas mudaria a receita.
- @dp.expect_all_or_fail só para o que nunca pode acontecer.
- Sempre rode databricks bundle validate --strict antes do deploy.

TABELAS SILVER
1. silver.produtos (chave id_produto): remove duplicatas por id_produto; trim em nome_produto;
   preco_atual em DECIMAL(10,2); faixa_preco = PREMIUM (> 1000), MEDIO (> 500) ou BASICO.
   Fail: id_produto preenchido, preco_atual > 0.
2. silver.clientes (chave id_cliente): remove duplicatas; guarda o nome original em nome_original;
   nome_cliente sem pronome de tratamento no início (Sr., Sra., Srta., Dr., Dra.) e em formato
   título; estado (UF) em maiúsculas; junta nome_estado e regiao a partir de bronze.estados_ibge.
   Fail: id_cliente preenchido, regiao preenchida.
3. silver.preco_competidores (chave id_produto + nome_concorrente): remove duplicatas;
   preco_concorrente em DECIMAL(10,2); data_coleta de texto para timestamp;
   preco_suspeito = true quando o preço do concorrente é menor que 60% do nosso preco_atual.
   Fail: id_produto preenchido, preço > 0. Warn: preco_plausivel = NOT preco_suspeito.
4. silver.vendas (chave id_venda): remove duplicatas; preco_unitario em DECIMAL(10,2);
   receita = quantidade × preco_unitario em DECIMAL(10,2); data (date), hora (0-23),
   dia_semana_num (1 = domingo ... 7 = sábado) e dia_semana em português (Domingo, Segunda,
   Terça, Quarta, Quinta, Sexta, Sábado); produto_cadastrado = false quando o id_produto não existe
   em silver.produtos; venda_antes_do_cadastro = true quando data_venda é anterior à data_criacao
   do produto.
   Fail: id_venda, data_venda, id_cliente, id_produto, quantidade e preco_unitario preenchidos;
   quantidade > 0; preco_unitario > 0; canal_venda em ('ecommerce', 'loja_fisica').
   Warn: produto_cadastrado; venda_depois_do_cadastro = NOT venda_antes_do_cadastro.

PLACAR DE QUALIDADE
Crie também gold.qualidade_dados em SQL (CREATE OR REFRESH MATERIALIZED VIEW), uma linha por regra,
com as colunas regra, tabela, severidade (ALERTA, INFORMATIVO ou CORRIGIDO), linhas_afetadas e
receita_afetada (só para regras sobre vendas). Regras:
- ALERTA: venda de produto não cadastrado; venda anterior à criação do produto; preço de concorrente
  abaixo de 60% do nosso; marca do produto diferente de outra marca citada no nome do produto.
- INFORMATIVO: produto com nome igual ao de outro produto; produto monitorado em menos de 4 concorrentes.
- CORRIGIDO: nome de cliente com pronome de tratamento.
Declare as colunas com tipo e COMMENT, e COMMENT na tabela.

NO FIM
Valide, faça o deploy em dev, rode o pipeline e acompanhe até terminar (se falhar, leia o erro e
corrija). Depois me mostre as métricas das expectations no event log e o gold.qualidade_dados.
Números esperados: 3.020 vendas, receita total R$ 974.077,28, 20 vendas de produto não cadastrado
(R$ 4.240,01), 5 vendas antes do cadastro (R$ 325,88), 55 preços suspeitos, 12 produtos com marca
incoerente, 137 com nome repetido, 109 com menos de 4 concorrentes, 11 clientes com pronome.
Clientes por região: Norte 17, Nordeste 12, Centro-Oeste 9, Sudeste 8, Sul 4.
