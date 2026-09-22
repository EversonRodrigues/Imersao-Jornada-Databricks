# Databricks notebook source
# MAGIC %md
# MAGIC # Aula 2 · Data lake → Bronze — gabarito
# MAGIC ### "De onde vieram esses dados?"
# MAGIC
# MAGIC Na Aula 1 você arrastou 4 arquivos CSV para dentro do Databricks. Funciona uma vez. Mas numa empresa os
# MAGIC arquivos não ficam no seu computador: eles ficam em um **storage na nuvem**, e chegam lá todo dia,
# MAGIC exportados pelos sistemas.
# MAGIC
# MAGIC O nosso data lake é o **Storage do Supabase**, que fala o mesmo protocolo do **Amazon S3**. O código que
# MAGIC você escreve hoje funciona igual na AWS.
# MAGIC
# MAGIC ```
# MAGIC  Storage do Supabase (S3)  ─┐
# MAGIC   vendas.parquet            ├─►  tabelas ecommerce.bronze.*
# MAGIC  API do IBGE (JSON)        ─┘     (Delta + metadados de ingestão)
# MAGIC ```
# MAGIC
# MAGIC > Este é o **gabarito**, com tudo escrito. O notebook `01_ingestao_bronze` tem as mesmas células com
# MAGIC > lacunas, para você preencher na aula.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Conectando no storage
# MAGIC
# MAGIC Quatro valores, copiados do Supabase em **Project Settings → Storage → S3 access keys**:

# COMMAND ----------

import boto3

S3_ENDPOINT = "https://pnkfrnjvvywiufphcqgw.storage.supabase.co/storage/v1/s3"
S3_REGION = "us-east-2"

ACCESS_KEY = "XXXX"
SECRET_KEY = "XXXX"

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    region_name=S3_REGION,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

# Listar buckets
response = s3.list_buckets()

for bucket in response["Buckets"]:
    print(bucket["Name"])

# COMMAND ----------

# MAGIC %md
# MAGIC Se os buckets apareceram, a conexão está certa e qualquer erro daqui para frente é do seu código.
# MAGIC
# MAGIC | Termo | O que é |
# MAGIC |---|---|
# MAGIC | **Bucket** | A "pasta raiz", o balde |
# MAGIC | **Key** | O caminho do arquivo dentro do bucket, por exemplo `vendas.parquet` |
# MAGIC | **Endpoint** | O endereço do serviço |
# MAGIC | **Access key / secret** | Usuário e senha da máquina |
# MAGIC
# MAGIC > Na aula, a chave fica no notebook para ser simples de ver. **Em produção, ela nunca fica**: vai para o
# MAGIC > secret scope (`dbutils.secrets.get("imersao", "s3_key")`), porque notebook vai para o Git. Isso entra
# MAGIC > na Aula 3.
# MAGIC
# MAGIC ## 2. O que tem dentro do bucket

# COMMAND ----------

BUCKET = "ecommerce"

response = s3.list_objects_v2(Bucket=BUCKET)

for objeto in response["Contents"]:
    print(f"{objeto['Key']:<30} {objeto['Size']:>10,} bytes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Baixando um arquivo
# MAGIC
# MAGIC O `get_object` devolve um dicionário; o conteúdo está em `Body`, e o `.read()` transforma em **bytes**.

# COMMAND ----------

objeto = s3.get_object(Bucket=BUCKET, Key="vendas.parquet")
conteudo = objeto["Body"].read()

print(f"{len(conteudo):,} bytes baixados")

# COMMAND ----------

# MAGIC %md
# MAGIC ### De bytes para tabela
# MAGIC
# MAGIC O pandas espera um arquivo, e o que temos são bytes na memória. O `io.BytesIO` finge ser um arquivo para
# MAGIC o pandas conseguir ler.

# COMMAND ----------

import io
import pandas as pd

df_vendas = pd.read_parquet(io.BytesIO(conteudo))

print(f"{len(df_vendas):,} linhas · colunas: {list(df_vendas.columns)}")
display(df_vendas.head())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Gravando na bronze
# MAGIC
# MAGIC Antes, a estrutura. Aproveitamos para **apagar as tabelas que você subiu na mão na Aula 1**: elas voltam
# MAGIC agora vindas do data lake.

# COMMAND ----------

CATALOGO = "ecommerce"
TABELAS = ["vendas", "produtos", "clientes", "preco_competidores"]

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOGO}")
for schema in ["bronze", "silver", "gold"]:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOGO}.{schema}")

for tabela in TABELAS:
    spark.sql(f"DROP TABLE IF EXISTS {CATALOGO}.bronze.{tabela}")

display(spark.sql(f"SHOW TABLES IN {CATALOGO}.bronze"))

# COMMAND ----------

# MAGIC %md
# MAGIC A bronze guarda o dado **como chegou**, mais duas colunas de controle que o arquivo original não tem:
# MAGIC
# MAGIC - `_ingerido_em`: quando o dado entrou;
# MAGIC - `_origem`: de onde ele veio.
# MAGIC
# MAGIC Com essas duas colunas você responde, daqui a três meses, a pergunta que todo mundo faz: *"esse número
# MAGIC está velho?"*. Nada é limpo aqui: limpeza é trabalho da silver, amanhã.
# MAGIC
# MAGIC O `spark.createDataFrame` converte o DataFrame do pandas em DataFrame do Spark, que é o que sabe gravar
# MAGIC em tabela Delta.

# COMMAND ----------

from pyspark.sql import functions as F

(
    spark.createDataFrame(df_vendas)
    .withColumn("_ingerido_em", F.current_timestamp())
    .withColumn("_origem", F.lit(f"s3://{BUCKET}/vendas.parquet"))
    .write.mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOGO}.bronze.vendas")
)

display(spark.table(f"{CATALOGO}.bronze.vendas").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Repetindo para as 4 tabelas
# MAGIC
# MAGIC E se fossem 4, 10 ou 100 arquivos? Copiar o bloco acima 100 vezes é pedir para errar. O `for` repete o
# MAGIC mesmo caminho para cada tabela.

# COMMAND ----------

for tabela in TABELAS:
    objeto = s3.get_object(Bucket=BUCKET, Key=f"{tabela}.parquet")
    df = pd.read_parquet(io.BytesIO(objeto["Body"].read()))

    (
        spark.createDataFrame(df)
        .withColumn("_ingerido_em", F.current_timestamp())
        .withColumn("_origem", F.lit(f"s3://{BUCKET}/{tabela}.parquet"))
        .write.mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{CATALOGO}.bronze.{tabela}")
    )

    print(f"✅ {tabela:<20} {spark.table(f'{CATALOGO}.bronze.{tabela}').count():>6,} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Uma fonte a mais: a API do IBGE
# MAGIC
# MAGIC A Diretora de Customer Success pediu a visão **por região**, mas o cadastro de clientes só tem a UF.
# MAGIC Nenhum arquivo interno resolve isso: o dado está fora da empresa.
# MAGIC
# MAGIC Repare que o padrão é o mesmo do S3: buscar na origem, olhar o que veio e gravar na bronze.

# COMMAND ----------

import requests

URL_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"

response = requests.get(URL_IBGE, timeout=60)
estados = response.json()

print(f"{len(estados)} estados recebidos. Exemplo:")
print(estados[0])

# COMMAND ----------

# MAGIC %md
# MAGIC O JSON tem um dicionário dentro do outro (`regiao`). O `pd.json_normalize` achata isso e transforma
# MAGIC `regiao.nome` em uma coluna.

# COMMAND ----------

df_estados = pd.json_normalize(estados)
df_estados.columns = [coluna.replace(".", "_") for coluna in df_estados.columns]

(
    spark.createDataFrame(df_estados)
    .withColumn("_ingerido_em", F.current_timestamp())
    .withColumn("_origem", F.lit(URL_IBGE))
    .write.mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOGO}.bronze.estados_ibge")
)

display(spark.table(f"{CATALOGO}.bronze.estados_ibge").limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Conferência

# COMMAND ----------

conferencia = " UNION ALL ".join(
    f"SELECT '{t}' AS tabela, COUNT(*) AS linhas, MAX(_origem) AS origem, MAX(_ingerido_em) AS ingerido_em "
    f"FROM {CATALOGO}.bronze.{t}"
    for t in TABELAS + ["estados_ibge"]
)
display(spark.sql(conferencia))

# COMMAND ----------

# MAGIC %md
# MAGIC Esperado: 3.020 vendas, 215 produtos, 50 clientes, 728 preços de concorrentes e 27 estados.
# MAGIC
# MAGIC ### O que você construiu aqui
# MAGIC
# MAGIC - Uma ingestão que **não depende de ninguém arrastar arquivo**.
# MAGIC - Metadados que respondem "de quando é esse dado, e de onde ele veio?".
# MAGIC - Duas fontes diferentes (um data lake S3 e uma API) no mesmo formato de saída.
# MAGIC
# MAGIC **Amanhã:** a Aula 3 limpa e organiza esse dado nas camadas silver e gold, com a ajuda do Claude Code, e
# MAGIC tira a chave de dentro do notebook.
