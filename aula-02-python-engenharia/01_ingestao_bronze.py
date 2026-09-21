# Databricks notebook source
# MAGIC %md
# MAGIC # Aula 2 · Parte 1: Ingestão → Bronze
# MAGIC ### "De onde vieram esses dados?"
# MAGIC
# MAGIC Na Aula 1 você baixou 4 CSVs e subiu na mão, direto como tabelas na bronze. Isso não escala: amanhã chega arquivo novo, e depois de amanhã também.
# MAGIC
# MAGIC Este notebook **substitui aquele upload manual**: ele recria as mesmas tabelas `bronze.vendas`, `bronze.produtos`, `bronze.clientes` e `bronze.preco_competidores`, agora de forma automática e com colunas de controle.
# MAGIC
# MAGIC Hoje o dado vai **chegar sozinho**. Este notebook busca os dados em duas fontes externas e grava na camada **bronze**:
# MAGIC
# MAGIC | Fonte | O que é | Formato |
# MAGIC |---|---|---|
# MAGIC | Data lake (GitHub) | Vendas, produtos, clientes e preços dos concorrentes | Parquet |
# MAGIC | API do IBGE | Estados brasileiros e suas regiões | JSON (REST) |
# MAGIC
# MAGIC ```
# MAGIC  fontes externas ──► volume ecommerce.bronze.arquivos/landing ──► tabelas ecommerce.bronze.*
# MAGIC   (HTTP / API)          (cópia fiel do arquivo)                (tabela Delta + metadados)
# MAGIC ```
# MAGIC
# MAGIC > **Acesso à internet na Free Edition:** para o Databricks acessar sites externos, a conta precisa estar **verificada**. Se a primeira célula de download der erro de conexão, verifique a conta pelo LinkedIn quando o Databricks pedir. Enquanto isso, suba os arquivos `.parquet` da pasta `dados/` para o volume `ecommerce.bronze.arquivos`, na subpasta `landing`, pela interface, e pule direto para a seção *Bronze*.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parâmetros
# MAGIC
# MAGIC Widgets deixam o notebook reutilizável: o mesmo código roda no Job e na aula, só mudando o valor.

# COMMAND ----------

dbutils.widgets.text("catalogo", "ecommerce")
dbutils.widgets.text(
    "url_base",
    "https://raw.githubusercontent.com/lvgalvao/Imersao-Jornada-Databricks/main/dados",
)

catalogo = dbutils.widgets.get("catalogo")
url_base = dbutils.widgets.get("url_base")

pasta_landing = f"/Volumes/{catalogo}/bronze/arquivos/landing"
print(f"Catálogo: {catalogo}")
print(f"Origem:   {url_base}")
print(f"Landing:  {pasta_landing}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Garantir que a estrutura existe
# MAGIC
# MAGIC Pipelines devem ser **idempotentes**: rodar duas vezes dá o mesmo resultado que rodar uma. Por isso usamos `IF NOT EXISTS`.

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalogo}")
for schema in ["bronze", "silver", "gold"]:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalogo}.{schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalogo}.bronze.arquivos")

dbutils.fs.mkdirs(pasta_landing)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Baixar arquivos do data lake
# MAGIC
# MAGIC Começamos com **um** arquivo, para entender cada passo.

# COMMAND ----------

import requests

url = f"{url_base}/vendas.parquet"
resposta = requests.get(url, timeout=60)
resposta.raise_for_status()  # para aqui se a resposta não for 200 OK

print(f"Status: {resposta.status_code}")
print(f"Tamanho: {len(resposta.content):,} bytes")

# COMMAND ----------

# MAGIC %md
# MAGIC Os bytes vão para o volume **sem nenhuma alteração**. Se amanhã a transformação tiver um bug, o arquivo original continua lá para reprocessar.

# COMMAND ----------

with open(f"{pasta_landing}/vendas.parquet", "wb") as arquivo:
    arquivo.write(resposta.content)

display(dbutils.fs.ls(pasta_landing))

# COMMAND ----------

# MAGIC %md
# MAGIC E se fossem 4, 10 ou 100 tabelas? Copiar o bloco acima 100 vezes é pedir para errar. O `for` repete o mesmo passo para cada tabela.

# COMMAND ----------

TABELAS = ["vendas", "produtos", "clientes", "preco_competidores"]


def baixar_para_landing(nome_arquivo: str) -> str:
    """Baixa um arquivo da origem e grava no volume. Retorna o caminho gravado."""
    resposta = requests.get(f"{url_base}/{nome_arquivo}", timeout=60)
    resposta.raise_for_status()
    destino = f"{pasta_landing}/{nome_arquivo}"
    with open(destino, "wb") as arquivo:
        arquivo.write(resposta.content)
    return destino


for tabela in TABELAS:
    caminho = baixar_para_landing(f"{tabela}.parquet")
    print(f"✅ {tabela:<20} → {caminho}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Consumir uma API REST
# MAGIC
# MAGIC A Diretora de Customer Success quer planejar a equipe **por região**, mas nosso cadastro só tem a UF. A API pública do IBGE devolve cada estado com a sua região.

# COMMAND ----------

import json

URL_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"

estados = requests.get(URL_IBGE, timeout=60).json()

print(f"{len(estados)} estados recebidos. Exemplo:")
print(json.dumps(estados[0], indent=2, ensure_ascii=False))

# COMMAND ----------

# MAGIC %md
# MAGIC A resposta é uma **lista de dicionários**, e dentro de cada um há outro dicionário (`regiao`). Guardamos o JSON como veio:

# COMMAND ----------

with open(f"{pasta_landing}/estados_ibge.json", "w", encoding="utf-8") as arquivo:
    json.dump(estados, arquivo, ensure_ascii=False)

display(dbutils.fs.ls(pasta_landing))

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## 3. Bronze: do arquivo para a tabela Delta
# MAGIC
# MAGIC A bronze guarda o dado **como chegou**, mais duas colunas de controle:
# MAGIC
# MAGIC - `_ingerido_em`: quando o dado entrou
# MAGIC - `_arquivo_origem`: de qual arquivo ele veio
# MAGIC
# MAGIC Nada é limpo aqui. Limpeza é trabalho da silver.

# COMMAND ----------

from pyspark.sql import functions as F

df_vendas = spark.read.parquet(f"{pasta_landing}/vendas.parquet")

df_vendas.printSchema()
display(df_vendas.limit(5))

# COMMAND ----------

def gravar_bronze(df, tabela: str) -> int:
    """Adiciona metadados de ingestão e sobrescreve a tabela bronze."""
    (
        df.withColumn("_ingerido_em", F.current_timestamp())
        .withColumn("_arquivo_origem", F.col("_metadata.file_path"))
        .write.mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{catalogo}.bronze.{tabela}")
    )
    return spark.table(f"{catalogo}.bronze.{tabela}").count()


for tabela in TABELAS:
    df = spark.read.parquet(f"{pasta_landing}/{tabela}.parquet")
    linhas = gravar_bronze(df, tabela)
    print(f"✅ {catalogo}.bronze.{tabela:<20} {linhas:>6,} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC O JSON do IBGE tem um dicionário dentro do outro. O Spark lê isso como uma coluna do tipo `struct`, e acessamos os campos internos com ponto: `regiao.nome`.

# COMMAND ----------

df_estados = spark.read.option("multiLine", "true").json(f"{pasta_landing}/estados_ibge.json")
df_estados.printSchema()

linhas = gravar_bronze(df_estados, "estados_ibge")
print(f"✅ {catalogo}.bronze.estados_ibge {linhas} linhas")

# COMMAND ----------

# Conferência: todas as tabelas bronze e quando foram ingeridas
conferencia = " UNION ALL ".join(
    f"SELECT '{t}' AS tabela, COUNT(*) AS linhas, MAX(_ingerido_em) AS ingerido_em FROM {catalogo}.bronze.{t}"
    for t in TABELAS + ["estados_ibge"]
)
display(spark.sql(conferencia))

# COMMAND ----------

# MAGIC %md
# MAGIC **Próximo passo:** `02_silver.py` limpa e padroniza esses dados.
