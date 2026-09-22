# Databricks notebook source
# MAGIC %md
# MAGIC # Aula 2 · Parte 1: Data lake → Bronze
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
# MAGIC   vendas.parquet            ├─► volume bronze.arquivos/landing ─► tabelas ecommerce.bronze.*
# MAGIC  API do IBGE (JSON)        ─┘      (cópia fiel do que chegou)       (Delta + metadados)
# MAGIC ```
# MAGIC
# MAGIC | Etapa | O que acontece |
# MAGIC |---|---|
# MAGIC | 1 | Apagamos as tabelas que você subiu na mão na Aula 1 |
# MAGIC | 2 | Conectamos no storage com `boto3`, a biblioteca de S3 |
# MAGIC | 3 | Listamos e baixamos os Parquet, guardando uma cópia no volume |
# MAGIC | 4 | Gravamos a camada bronze, com metadados de ingestão |
# MAGIC | 5 | Enriquecemos com a API do IBGE |
# MAGIC
# MAGIC > **Antes de começar:** faça o `00_esquenta_python` se você nunca programou em Python.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parâmetros
# MAGIC
# MAGIC Widgets deixam o notebook reutilizável: o mesmo código roda na aula e no Job, mudando só os valores.
# MAGIC
# MAGIC | Widget | Para que serve |
# MAGIC |---|---|
# MAGIC | `catalogo` | Catálogo do Unity Catalog (padrão `ecommerce`) |
# MAGIC | `origem` | `supabase` (o normal) ou `arquivos` (plano B, lê os Parquet do GitHub) |
# MAGIC | `url_base` | Endereço dos Parquet usados pelo plano B |
# MAGIC
# MAGIC Os dados do seu bucket ficam nas **constantes** da célula seguinte: copie do Supabase e cole ali. As
# MAGIC **chaves de acesso** não entram no notebook: ficam no secret scope (veja a seção 2).

# COMMAND ----------

# ---------------------------------------------------------------------------
# Copie estes três valores do Supabase:
#   Project Settings → Storage → S3 access keys (endpoint e região)
#   Storage → o nome do bucket que você criou
# ---------------------------------------------------------------------------
S3_ENDPOINT = "https://pnkfrnjvvywiufphcqgw.storage.supabase.co/storage/v1/s3"
S3_BUCKET = "ecommerce"
S3_REGION = "us-east-2"

dbutils.widgets.text("catalogo", "ecommerce")
dbutils.widgets.dropdown("origem", "supabase", ["supabase", "arquivos"])
dbutils.widgets.text(
    "url_base",
    "https://raw.githubusercontent.com/lvgalvao/Imersao-Jornada-Databricks/main/dados",
)

catalogo = dbutils.widgets.get("catalogo")
origem = dbutils.widgets.get("origem")
url_base = dbutils.widgets.get("url_base")

pasta_landing = f"/Volumes/{catalogo}/bronze/arquivos/landing"
TABELAS = ["vendas", "produtos", "clientes", "preco_competidores"]

print(f"Catálogo: {catalogo}")
print(f"Origem:   {origem}")
print(f"Bucket:   {S3_BUCKET} ({S3_REGION})")
print(f"Landing:  {pasta_landing}")

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

spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalogo}")
for schema in ["bronze", "silver", "gold"]:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalogo}.{schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalogo}.bronze.arquivos")
dbutils.fs.mkdirs(pasta_landing)

for tabela in TABELAS:
    spark.sql(f"DROP TABLE IF EXISTS {catalogo}.bronze.{tabela}")

display(spark.sql(f"SHOW TABLES IN {catalogo}.bronze"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Conectando no data lake com boto3
# MAGIC
# MAGIC **S3** (*Simple Storage Service*) é o serviço de arquivos da AWS, e virou o padrão do mercado: quase todo
# MAGIC storage na nuvem hoje aceita o mesmo protocolo. O Storage do Supabase é um deles.
# MAGIC
# MAGIC O vocabulário é curto:
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

s3 = None
if origem == "supabase":
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
# MAGIC Todo pipeline que fala com um sistema externo deveria começar com um teste barato. Se a listagem responde,
# MAGIC a conexão e as credenciais estão certas, e qualquer erro daqui para frente é do seu código.
# MAGIC
# MAGIC A resposta do `list_objects_v2` é um dicionário. Os arquivos ficam na chave `Contents`, que é uma lista de
# MAGIC dicionários, um por arquivo, com `Key` (o nome) e `Size` (o tamanho em bytes).

# COMMAND ----------

if s3 is not None:
    resposta = s3.list_objects_v2(Bucket=S3_BUCKET)

    for objeto in resposta.get("Contents", []):
        print(f"{objeto['Key']:<30} {objeto['Size']:>10,} bytes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Baixando um arquivo
# MAGIC
# MAGIC Começamos com **um** arquivo, para entender cada passo. O `get_object` devolve outro dicionário; o
# MAGIC conteúdo do arquivo está em `Body`, e o `.read()` transforma em **bytes**.
# MAGIC
# MAGIC Esses bytes vão direto para o volume, **sem nenhuma alteração**. Se amanhã a transformação tiver um bug, o
# MAGIC arquivo original continua lá para reprocessar, e você não precisa incomodar o sistema de origem.

# COMMAND ----------

def baixar_do_s3(nome_arquivo: str) -> bytes:
    """Baixa um arquivo do bucket e devolve os bytes."""
    objeto = s3.get_object(Bucket=S3_BUCKET, Key=nome_arquivo)
    return objeto["Body"].read()


def baixar_do_github(nome_arquivo: str) -> bytes:
    """Plano B: baixa o mesmo arquivo publicado no repositório."""
    import requests

    resposta = requests.get(f"{url_base}/{nome_arquivo}", timeout=60)
    resposta.raise_for_status()
    return resposta.content


def baixar(nome_arquivo: str) -> bytes:
    return baixar_do_s3(nome_arquivo) if origem == "supabase" else baixar_do_github(nome_arquivo)


conteudo = baixar("vendas.parquet")
print(f"{len(conteudo):,} bytes baixados")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Olhando o que veio, antes de gravar
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
# MAGIC ### Gravando a cópia no volume (a pasta *landing*)
# MAGIC
# MAGIC Escrever bytes no volume é igual a escrever qualquer arquivo em Python: `open(caminho, "wb")`, onde o
# MAGIC `"wb"` quer dizer *write binary*.

# COMMAND ----------

def guardar_no_landing(conteudo: bytes, nome_arquivo: str) -> str:
    """Grava os bytes recebidos no volume, sem alterar nada. Devolve o caminho."""
    destino = f"{pasta_landing}/{nome_arquivo}"
    with open(destino, "wb") as arquivo:
        arquivo.write(conteudo)
    return destino


print(guardar_no_landing(conteudo, "vendas.parquet"))
display(dbutils.fs.ls(pasta_landing))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Bronze: do arquivo para a tabela Delta
# MAGIC
# MAGIC A bronze guarda o dado **como chegou**, mais duas colunas de controle que o arquivo original não tem:
# MAGIC
# MAGIC - `_ingerido_em`: quando o dado entrou;
# MAGIC - `_origem`: de onde ele veio.
# MAGIC
# MAGIC Com essas duas colunas você responde, daqui a três meses, a pergunta que todo mundo faz: *"esse número
# MAGIC está velho?"*. Nada é limpo aqui: limpeza é trabalho da silver.

# COMMAND ----------

from pyspark.sql import functions as F


def gravar_bronze(tabela: str) -> int:
    """Lê o Parquet do landing, acrescenta metadados e sobrescreve a tabela bronze."""
    (
        spark.read.parquet(f"{pasta_landing}/{tabela}.parquet")
        .withColumn("_ingerido_em", F.current_timestamp())
        .withColumn("_origem", F.lit(origem))
        .write.mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{catalogo}.bronze.{tabela}")
    )
    return spark.table(f"{catalogo}.bronze.{tabela}").count()


print(f"{catalogo}.bronze.vendas: {gravar_bronze('vendas'):,} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Repetindo para as 4 tabelas
# MAGIC
# MAGIC E se fossem 4, 10 ou 100 arquivos? Copiar o bloco acima 100 vezes é pedir para errar. O `for` que você
# MAGIC treinou no esquenta repete o mesmo caminho para cada tabela.

# COMMAND ----------

for tabela in TABELAS:
    conteudo = baixar(f"{tabela}.parquet")
    guardar_no_landing(conteudo, f"{tabela}.parquet")
    linhas = gravar_bronze(tabela)
    print(f"✅ {tabela:<20} {linhas:>6,} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Uma fonte a mais: a API do IBGE
# MAGIC
# MAGIC A Diretora de Customer Success pediu a visão **por região**, mas o cadastro de clientes só tem a UF.
# MAGIC Nenhum arquivo interno resolve isso: o dado está fora da empresa.
# MAGIC
# MAGIC A API pública do IBGE devolve os 27 estados com a sua região, em JSON. Repare que o padrão é o mesmo do
# MAGIC S3: buscar na origem, guardar no landing, gravar na bronze.

# COMMAND ----------

import json
import requests

URL_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"

resposta = requests.get(URL_IBGE, timeout=60)
resposta.raise_for_status()
estados = resposta.json()

print(f"{len(estados)} estados recebidos. Exemplo:")
print(json.dumps(estados[0], indent=2, ensure_ascii=False))

with open(f"{pasta_landing}/estados_ibge.json", "w", encoding="utf-8") as arquivo:
    json.dump(estados, arquivo, ensure_ascii=False)

# COMMAND ----------

# MAGIC %md
# MAGIC O JSON tem um dicionário dentro do outro (`regiao`). O Spark lê isso como uma coluna do tipo `struct`, e
# MAGIC acessamos os campos internos com ponto: `regiao.nome`. Quem achata essa estrutura é a silver.

# COMMAND ----------

df_estados = spark.read.option("multiLine", "true").json(f"{pasta_landing}/estados_ibge.json")
df_estados.printSchema()

(
    df_estados
    .withColumn("_ingerido_em", F.current_timestamp())
    .withColumn("_origem", F.lit("api_ibge"))
    .write.mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{catalogo}.bronze.estados_ibge")
)
print(f"{catalogo}.bronze.estados_ibge: {spark.table(f'{catalogo}.bronze.estados_ibge').count()} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Conferência
# MAGIC
# MAGIC As tabelas que você apagou no começo voltaram, agora com a marca de quando e de onde vieram.

# COMMAND ----------

conferencia = " UNION ALL ".join(
    f"SELECT '{t}' AS tabela, COUNT(*) AS linhas, MAX(_origem) AS origem, MAX(_ingerido_em) AS ingerido_em "
    f"FROM {catalogo}.bronze.{t}"
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
# MAGIC - Uma cópia fiel do que chegou, guardada no volume, para reprocessar quando precisar.
# MAGIC - Metadados que respondem "de quando é esse dado?".
# MAGIC - Duas fontes diferentes (um data lake S3 e uma API) no mesmo formato de saída.
# MAGIC
# MAGIC **Próximo passo:** `02_silver.py` limpa, padroniza e enriquece esses dados.
