# Databricks notebook source
# MAGIC %md
# MAGIC # Aula 2 · Parte 1: Supabase → Bronze
# MAGIC ### "De onde vieram esses dados?"
# MAGIC
# MAGIC Na Aula 1 você arrastou 4 arquivos CSV para dentro do Databricks. Funciona uma vez. Mas os dados de uma
# MAGIC empresa não moram em CSV: eles moram no **banco de dados do sistema que roda a operação**.
# MAGIC
# MAGIC No nosso caso, o e-commerce roda em cima de um **Postgres hospedado no Supabase (AWS)**. É de lá que os
# MAGIC dados vão sair hoje, sozinhos.
# MAGIC
# MAGIC ```
# MAGIC  Supabase (Postgres na AWS)  ─┐
# MAGIC                               ├─► volume bronze.arquivos/landing ─► tabelas ecommerce.bronze.*
# MAGIC  API do IBGE (JSON)          ─┘        (cópia fiel do que chegou)      (Delta + metadados)
# MAGIC ```
# MAGIC
# MAGIC | Etapa | O que acontece |
# MAGIC |---|---|
# MAGIC | 1 | Apagamos as tabelas que você subiu na mão na Aula 1 |
# MAGIC | 2 | Conectamos no Postgres do Supabase com SQLAlchemy |
# MAGIC | 3 | Lemos as 4 tabelas e guardamos uma cópia em Parquet no volume |
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
# MAGIC | `supabase_uri` | A connection URI. Deixe vazio para usar o segredo `imersao/supabase_uri` |
# MAGIC | `url_base` | Endereço dos Parquet usados pelo plano B |

# COMMAND ----------

dbutils.widgets.text("catalogo", "ecommerce")
dbutils.widgets.dropdown("origem", "supabase", ["supabase", "arquivos"])
dbutils.widgets.text("supabase_uri", "")
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
print(f"Landing:  {pasta_landing}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Apagando o trabalho manual da Aula 1
# MAGIC
# MAGIC Vamos jogar fora as tabelas que você subiu na mão. Pode apagar sem medo: no fim deste notebook elas
# MAGIC voltam, agora vindas do banco de origem e prontas para se atualizar sozinhas todo dia.
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
# MAGIC ## 2. Conectando no Postgres do Supabase
# MAGIC
# MAGIC Precisamos de duas bibliotecas: o **SQLAlchemy**, que cria a conexão, e o **psycopg2**, que é o driver
# MAGIC que fala a língua do Postgres.

# COMMAND ----------

# MAGIC %pip install --quiet sqlalchemy psycopg2-binary

# COMMAND ----------

# MAGIC %md
# MAGIC ### A connection URI
# MAGIC
# MAGIC No Supabase, em **Connect**, existem três modos de conexão. A escolha importa:
# MAGIC
# MAGIC | Modo | Porta | Quando usar |
# MAGIC |---|---|---|
# MAGIC | **Session pooler** | 5432 | **O nosso caso.** Funciona em rede IPv4, que é a do Databricks serverless |
# MAGIC | Transaction pooler | 6543 | Funções serverless de vida muito curta; pode atrapalhar drivers que usam *prepared statements* |
# MAGIC | Direct connection | 5432 | Servidor fixo com IPv6 (ou com o add-on pago de IPv4) |
# MAGIC
# MAGIC A URI do Session pooler tem este formato:
# MAGIC
# MAGIC ```
# MAGIC postgresql+psycopg2://postgres.<ref>:<senha>@aws-0-<regiao>.pooler.supabase.com:5432/postgres?sslmode=require
# MAGIC ```
# MAGIC
# MAGIC > **Nunca cole a senha no notebook.** Notebook vai para o Git, e senha em repositório é incidente de
# MAGIC > segurança. Guarde no **secret scope** do Databricks, pela CLI:
# MAGIC >
# MAGIC > ```bash
# MAGIC > databricks secrets create-scope imersao
# MAGIC > databricks secrets put-secret imersao supabase_uri
# MAGIC > ```
# MAGIC >
# MAGIC > O `dbutils.secrets.get` lê o valor, e o Databricks substitui o segredo por `[REDACTED]` em qualquer
# MAGIC > saída impressa.

# COMMAND ----------

def obter_uri() -> str:
    """Pega a URI do widget; se estiver vazio, tenta o segredo."""
    uri = dbutils.widgets.get("supabase_uri")
    if uri:
        return uri
    try:
        return dbutils.secrets.get("imersao", "supabase_uri")
    except Exception:
        return ""


engine = None
if origem == "supabase":
    from sqlalchemy import create_engine

    uri = obter_uri()
    if not uri:
        raise ValueError(
            "Sem URI do Supabase. Preencha o widget supabase_uri, crie o segredo imersao/supabase_uri "
            "ou mude o widget origem para 'arquivos'."
        )
    engine = create_engine(uri, pool_pre_ping=True)
    print("Engine criada.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Testando a conexão antes de confiar nela
# MAGIC
# MAGIC Todo pipeline que fala com um sistema externo deveria começar com um teste barato. Se o `SELECT 1` não
# MAGIC responde, o problema é de conexão, e não do seu código.

# COMMAND ----------

import pandas as pd

if engine is not None:
    display(pd.read_sql("SELECT 1 AS conexao_ok", engine))

    # quais tabelas existem no banco de origem?
    tabelas_no_banco = pd.read_sql(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name",
        engine,
    )
    display(tabelas_no_banco)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Lendo uma tabela e guardando o original
# MAGIC
# MAGIC Começamos com **uma** tabela, para entender cada passo. O `pandas` executa o SQL pela engine e devolve um
# MAGIC DataFrame.
# MAGIC
# MAGIC Antes de transformar qualquer coisa, gravamos uma cópia fiel em **Parquet** no volume (a pasta *landing*).
# MAGIC Se amanhã a transformação tiver um bug, o dado original continua lá, e você reprocessa sem incomodar o
# MAGIC banco de produção.

# COMMAND ----------

def ler_do_supabase(tabela: str) -> pd.DataFrame:
    """Lê a tabela inteira do Postgres e devolve um DataFrame do pandas."""
    return pd.read_sql(f"SELECT * FROM {tabela}", engine)


def ler_do_github(tabela: str) -> pd.DataFrame:
    """Plano B: lê o Parquet publicado no repositório."""
    return pd.read_parquet(f"{url_base}/{tabela}.parquet")


def ler_origem(tabela: str) -> pd.DataFrame:
    return ler_do_supabase(tabela) if origem == "supabase" else ler_do_github(tabela)


df_vendas = ler_origem("vendas")
print(f"{len(df_vendas):,} linhas · colunas: {list(df_vendas.columns)}")
display(df_vendas.head())

# COMMAND ----------

def guardar_no_landing(df: pd.DataFrame, tabela: str) -> str:
    """Grava a cópia bruta em Parquet no volume e devolve o caminho."""
    destino = f"{pasta_landing}/{tabela}.parquet"
    df.to_parquet(destino, index=False)
    return destino


print(guardar_no_landing(df_vendas, "vendas"))
display(dbutils.fs.ls(pasta_landing))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Bronze: do arquivo para a tabela Delta
# MAGIC
# MAGIC A bronze guarda o dado **como chegou**, mais duas colunas de controle que o dado original não tem:
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
# MAGIC E se fossem 4, 10 ou 100 tabelas? Copiar o bloco acima 100 vezes é pedir para errar. O `for` que você
# MAGIC treinou no esquenta repete o mesmo caminho para cada tabela.

# COMMAND ----------

for tabela in TABELAS:
    df = ler_origem(tabela)
    guardar_no_landing(df, tabela)
    linhas = gravar_bronze(tabela)
    print(f"✅ {tabela:<20} {linhas:>6,} linhas")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Uma fonte a mais: a API do IBGE
# MAGIC
# MAGIC A Diretora de Customer Success pediu a visão **por região**, mas o cadastro de clientes só tem a UF.
# MAGIC Nenhum banco interno resolve isso: o dado está fora da empresa.
# MAGIC
# MAGIC A API pública do IBGE devolve os 27 estados com a sua região, em JSON.

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
# MAGIC - Duas fontes diferentes (um banco e uma API) no mesmo formato de saída.
# MAGIC
# MAGIC **Próximo passo:** `02_silver.py` limpa, padroniza e enriquece esses dados.
