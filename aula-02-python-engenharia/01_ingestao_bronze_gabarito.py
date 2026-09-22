# Databricks notebook source
# MAGIC %md
# MAGIC # Aula 2 · Parte 1: Data lake → Bronze — gabarito
# MAGIC ### "De onde vieram esses dados?"
# MAGIC
# MAGIC Na Aula 1 você arrastou 4 arquivos CSV para dentro do Databricks. Funciona uma vez. Mas numa empresa os
# MAGIC arquivos não ficam no seu computador: eles ficam em um **storage na nuvem**, e chegam lá todo dia,
# MAGIC exportados pelos sistemas.
# MAGIC
# MAGIC O nosso data lake é o **Storage do Supabase**, que fala o mesmo protocolo do **Amazon S3**. Ou seja: o
# MAGIC código que você escreve hoje funciona igual na AWS, e é isso que as empresas usam.
# MAGIC
# MAGIC ```
# MAGIC  Storage do Supabase (S3)  ─┐
# MAGIC   vendas.parquet            ├─►  tabelas ecommerce.bronze.*
# MAGIC  API do IBGE (JSON)        ─┘     (Delta + metadados de ingestão)
# MAGIC ```
# MAGIC
# MAGIC | Etapa | O que acontece |
# MAGIC |---|---|
# MAGIC | 1 | Apagamos as tabelas que você subiu na mão na Aula 1 |
# MAGIC | 2 | Conectamos no storage com `boto3`, a biblioteca de S3 |
# MAGIC | 3 | Listamos e baixamos os Parquet |
# MAGIC | 4 | Gravamos a camada bronze, com metadados de ingestão |
# MAGIC | 5 | Enriquecemos com a API do IBGE |
# MAGIC
# MAGIC > Este é o **gabarito**, com o pipeline inteiro escrito. O notebook `01_ingestao_bronze` tem as mesmas
# MAGIC > células com lacunas, para você escrever. É ele que roda na aula ao vivo.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuração
# MAGIC
# MAGIC Três valores do seu bucket, o catálogo e a lista de tabelas. As **chaves de acesso** não entram aqui:
# MAGIC ficam no secret scope (veja a seção 2).

# COMMAND ----------

# ---------------------------------------------------------------------------
# Copie estes valores do Supabase:
#   Project Settings → Storage → S3 access keys (endpoint e região)
#   Storage → o nome do bucket que você criou
# ---------------------------------------------------------------------------
S3_ENDPOINT = "https://pnkfrnjvvywiufphcqgw.storage.supabase.co/storage/v1/s3"
S3_BUCKET = "ecommerce"
S3_REGION = "us-east-2"

CATALOGO = "ecommerce"
TABELAS = ["vendas", "produtos", "clientes", "preco_competidores"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Apagando o trabalho manual da Aula 1
# MAGIC
# MAGIC Vamos jogar fora as tabelas que você subiu na mão. Pode apagar sem medo: no fim deste notebook elas
# MAGIC voltam, agora vindas do data lake e prontas para se atualizar sozinhas todo dia.
# MAGIC
# MAGIC **Essa é a diferença entre um analista e um engenheiro de dados:** o analista carrega o arquivo; o
# MAGIC engenheiro constrói o caminho por onde o arquivo passa sozinho.

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOGO}")
for schema in ["bronze", "silver", "gold"]:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOGO}.{schema}")

for tabela in TABELAS:
    spark.sql(f"DROP TABLE IF EXISTS {CATALOGO}.bronze.{tabela}")

display(spark.sql(f"SHOW TABLES IN {CATALOGO}.bronze"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Conectando no data lake com boto3
# MAGIC
# MAGIC **S3** (*Simple Storage Service*) é o serviço de arquivos da AWS, e virou o padrão do mercado: quase todo
# MAGIC storage na nuvem hoje aceita o mesmo protocolo. O Storage do Supabase é um deles.
# MAGIC
# MAGIC | Termo | O que é | Aqui |
# MAGIC |---|---|---|
# MAGIC | **Bucket** | A "pasta raiz", o balde | `ecommerce` |
# MAGIC | **Key** | O caminho do arquivo dentro do bucket | `vendas.parquet` |
# MAGIC | **Endpoint** | O endereço do serviço | `https://<ref>.storage.supabase.co/storage/v1/s3` |
# MAGIC | **Access key / secret** | Usuário e senha da máquina | Criados em *Project Settings → Storage → S3 access keys* |
# MAGIC
# MAGIC A biblioteca **`boto3`** é a da AWS. Mudando o `endpoint_url`, ela fala com qualquer storage compatível.
# MAGIC
# MAGIC > **Nunca cole chave de acesso no notebook.** Notebook vai para o Git, e credencial em repositório é
# MAGIC > incidente de segurança. Guarde no **secret scope** do Databricks, pela CLI:
# MAGIC >
# MAGIC > ```bash
# MAGIC > databricks secrets create-scope imersao
# MAGIC > databricks secrets put-secret imersao s3_key
# MAGIC > databricks secrets put-secret imersao s3_secret
# MAGIC > ```
# MAGIC >
# MAGIC > O `dbutils.secrets.get` lê o valor, e o Databricks troca o segredo por `[REDACTED]` em qualquer saída
# MAGIC > impressa.

# COMMAND ----------

import boto3

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    region_name=S3_REGION,
    aws_access_key_id=dbutils.secrets.get("imersao", "s3_key"),
    aws_secret_access_key=dbutils.secrets.get("imersao", "s3_secret"),
)
print(f"Cliente S3 criado em {S3_ENDPOINT}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### O que existe no bucket?
# MAGIC
# MAGIC Todo pipeline que fala com um sistema externo deveria começar com um teste barato. Se a listagem
# MAGIC responde, a conexão e as credenciais estão certas, e qualquer erro daqui para frente é do seu código.
# MAGIC
# MAGIC A resposta do `list_objects_v2` é um dicionário. Os arquivos ficam na chave `Contents`, que é uma lista
# MAGIC de dicionários, um por arquivo, com `Key` (o nome) e `Size` (o tamanho em bytes).

# COMMAND ----------

resposta = s3.list_objects_v2(Bucket=S3_BUCKET)

for objeto in resposta.get("Contents", []):
    print(f"{objeto['Key']:<30} {objeto['Size']:>10,} bytes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Baixando um arquivo
# MAGIC
# MAGIC Começamos com **um** arquivo, para entender cada passo. O `get_object` devolve outro dicionário; o
# MAGIC conteúdo do arquivo está em `Body`, e o `.read()` transforma em **bytes**.

# COMMAND ----------

objeto = s3.get_object(Bucket=S3_BUCKET, Key="vendas.parquet")
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
# MAGIC ## 4. Bronze: gravando a tabela Delta
# MAGIC
# MAGIC A bronze guarda o dado **como chegou**, mais duas colunas de controle que o arquivo original não tem:
# MAGIC
# MAGIC - `_ingerido_em`: quando o dado entrou;
# MAGIC - `_origem`: de onde ele veio.
# MAGIC
# MAGIC Com essas duas colunas você responde, daqui a três meses, a pergunta que todo mundo faz: *"esse número
# MAGIC está velho?"*. Nada é limpo aqui: limpeza é trabalho da silver.
# MAGIC
# MAGIC O `spark.createDataFrame` converte o DataFrame do pandas em DataFrame do Spark, que é o que sabe gravar
# MAGIC em tabela Delta.

# COMMAND ----------

from pyspark.sql import functions as F

(
    spark.createDataFrame(df_vendas)
    .withColumn("_ingerido_em", F.current_timestamp())
    .withColumn("_origem", F.lit(f"s3://{S3_BUCKET}/vendas.parquet"))
    .write.mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOGO}.bronze.vendas")
)

print(f"{CATALOGO}.bronze.vendas: {spark.table(f'{CATALOGO}.bronze.vendas').count():,} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Repetindo para as 4 tabelas
# MAGIC
# MAGIC E se fossem 4, 10 ou 100 arquivos? Copiar o bloco acima 100 vezes é pedir para errar. O `for` que você
# MAGIC treinou no esquenta repete o mesmo caminho para cada tabela.

# COMMAND ----------

for tabela in TABELAS:
    objeto = s3.get_object(Bucket=S3_BUCKET, Key=f"{tabela}.parquet")
    df = pd.read_parquet(io.BytesIO(objeto["Body"].read()))

    (
        spark.createDataFrame(df)
        .withColumn("_ingerido_em", F.current_timestamp())
        .withColumn("_origem", F.lit(f"s3://{S3_BUCKET}/{tabela}.parquet"))
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
# MAGIC A API pública do IBGE devolve os 27 estados com a sua região, em JSON. Repare que o padrão é o mesmo do
# MAGIC S3: buscar na origem e gravar na bronze.

# COMMAND ----------

import requests

URL_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"

resposta = requests.get(URL_IBGE, timeout=60)
resposta.raise_for_status()
estados = resposta.json()

print(f"{len(estados)} estados recebidos. Exemplo:")
print(estados[0])

# COMMAND ----------

# MAGIC %md
# MAGIC O JSON tem um dicionário dentro do outro (`regiao`). Achatamos com `pd.json_normalize`, que transforma
# MAGIC `regiao.nome` em uma coluna. Quem trata isso de vez é a silver.

# COMMAND ----------

df_estados = pd.json_normalize(estados)
df_estados.columns = [c.replace(".", "_") for c in df_estados.columns]
print(list(df_estados.columns))

(
    spark.createDataFrame(df_estados)
    .withColumn("_ingerido_em", F.current_timestamp())
    .withColumn("_origem", F.lit(URL_IBGE))
    .write.mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOGO}.bronze.estados_ibge")
)

print(f"{CATALOGO}.bronze.estados_ibge: {spark.table(f'{CATALOGO}.bronze.estados_ibge').count()} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Conferência
# MAGIC
# MAGIC As tabelas que você apagou no começo voltaram, agora com a marca de quando e de onde vieram.

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
# MAGIC **Amanhã:** a Aula 3 limpa e organiza esse dado nas camadas silver e gold, com a ajuda do Claude Code.
