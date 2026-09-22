# Databricks notebook source
# MAGIC %md
# MAGIC # Aula 2 · Esquenta de Python — gabarito
# MAGIC
# MAGIC As 10 respostas do notebook `00_esquenta_python`, comentadas. Existe mais de um caminho certo: se o seu
# MAGIC código faz a mesma coisa de outro jeito, está certo também.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Variáveis e tipos

# COMMAND ----------

nome_tabela = "vendas"          # str  · texto sempre entre aspas
total_vendas = 3020             # int  · número inteiro, sem aspas
receita_total = 974077.28       # float· número com casas decimais (ponto, não vírgula)
pipeline_ativo = True           # bool · True ou False, com inicial maiúscula

for valor in (nome_tabela, total_vendas, receita_total, pipeline_ativo):
    print(valor, type(valor))

# COMMAND ----------

# MAGIC %md
# MAGIC ### f-string
# MAGIC
# MAGIC O `f` antes das aspas liga a interpolação; o que está entre chaves é avaliado como código.

# COMMAND ----------

print(f"A tabela {nome_tabela} tem {total_vendas} linhas.")

# formatando número: milhar com ponto e 2 casas decimais
print(f"Receita: R$ {receita_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Listas

# COMMAND ----------

tabelas = ["vendas", "produtos", "clientes", "preco_competidores"]

print(f"São {len(tabelas)} tabelas")
print("Primeira:", tabelas[0])
print("Última:  ", tabelas[-1])     # índice negativo conta de trás para frente

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Dicionários

# COMMAND ----------

venda = {
    "id_venda": "sal_adff6978b0c6",
    "canal": "loja_fisica",
    "quantidade": 2,
    "preco_unitario": 64.79,
}

receita = venda["quantidade"] * venda["preco_unitario"]
print(f"Receita da venda {venda['id_venda']}: R$ {receita:.2f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Dicionário dentro de dicionário
# MAGIC
# MAGIC Leia de fora para dentro: `estado["regiao"]` devolve outro dicionário, e nele pedimos `["nome"]`.

# COMMAND ----------

estado = {"sigla": "AM", "nome": "Amazonas", "regiao": {"id": 1, "sigla": "N", "nome": "Norte"}}

print(estado["regiao"]["nome"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. `for` e `if`

# COMMAND ----------

tabelas = ["vendas", "produtos", "clientes", "preco_competidores"]

for tabela in tabelas:
    print(f"Baixando {tabela}.parquet do data lake...")

# COMMAND ----------

quantidades = [1, 3, 2, 5, 1]

for quantidade in quantidades:
    if quantidade > 2:
        print(f"{quantidade} unidades: venda grande")
    else:
        print(f"{quantidade} unidades: venda pequena")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Funções
# MAGIC
# MAGIC `def` cria a função, os parâmetros vão entre parênteses e o `return` devolve o resultado. O texto entre
# MAGIC três aspas é a documentação da função.

# COMMAND ----------

def calcular_receita(quantidade, preco_unitario):
    """Receita de uma venda, arredondada em 2 casas."""
    return round(quantidade * preco_unitario, 2)


print(calcular_receita(2, 64.79))      # 129.58
print(calcular_receita(1, 1286.09))    # 1286.09

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Bibliotecas

# COMMAND ----------

import requests
import pandas as pd

print("pandas", pd.__version__)
print("requests", requests.__version__)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Consumindo uma API
# MAGIC
# MAGIC `status_code` 200 significa "deu certo". O `raise_for_status()` interrompe a execução se vier erro, o que
# MAGIC evita seguir o pipeline com dado vazio.

# COMMAND ----------

URL_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"

resposta = requests.get(URL_IBGE, timeout=60)
resposta.raise_for_status()

estados = resposta.json()          # JSON vira lista de dicionários

print("status:", resposta.status_code)
print("estados recebidos:", len(estados))
print("primeiro:", estados[0])

# COMMAND ----------

# MAGIC %md
# MAGIC Montando a lista só com o que interessa. As duas formas abaixo fazem a mesma coisa: a primeira com `for`,
# MAGIC a segunda com *list comprehension*, que é o jeito curto de escrever o mesmo laço.

# COMMAND ----------

# forma 1: for tradicional
linhas = []
for estado in estados:
    linhas.append({
        "sigla": estado["sigla"],
        "nome": estado["nome"],
        "regiao": estado["regiao"]["nome"],
    })

# forma 2: list comprehension (mesmo resultado, uma linha)
linhas = [{"sigla": e["sigla"], "nome": e["nome"], "regiao": e["regiao"]["nome"]} for e in estados]

df_estados = pd.DataFrame(linhas)
display(df_estados.head())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. pandas

# COMMAND ----------

print("formato (linhas, colunas):", df_estados.shape)
print("colunas:", list(df_estados.columns))

# contagem por região: o GROUP BY do pandas
por_regiao = df_estados.groupby("regiao").size().sort_values(ascending=False)
print(por_regiao)

# filtro: o WHERE do pandas
display(df_estados[df_estados["regiao"] == "Norte"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. boto3: lendo arquivos do data lake
# MAGIC
# MAGIC O Storage do Supabase é compatível com o protocolo S3 da AWS, então o mesmo `boto3` funciona: muda apenas
# MAGIC o `endpoint_url`. As chaves ficam em **Project Settings → Storage → S3 access keys** e são guardadas no
# MAGIC secret scope do Databricks, nunca no notebook.

# COMMAND ----------

dbutils.widgets.text("s3_endpoint", "")
dbutils.widgets.text("s3_bucket", "ecommerce")
dbutils.widgets.text("s3_region", "us-east-2")

endpoint = dbutils.widgets.get("s3_endpoint")
bucket = dbutils.widgets.get("s3_bucket")

if not endpoint:
    print("Sem endpoint: preencha o widget s3_endpoint para rodar esta célula.")
else:
    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,                                   # https://<ref>.storage.supabase.co/storage/v1/s3
        region_name=dbutils.widgets.get("s3_region"),
        aws_access_key_id=dbutils.secrets.get("imersao", "s3_key"),
        aws_secret_access_key=dbutils.secrets.get("imersao", "s3_secret"),
    )

    # a resposta é um dicionário; os arquivos ficam na chave "Contents"
    resposta = s3.list_objects_v2(Bucket=bucket)

    for objeto in resposta.get("Contents", []):
        print(f"{objeto['Key']:<30} {objeto['Size']:>10,} bytes")

    # a forma curta, com list comprehension
    arquivos = [obj["Key"] for obj in resposta.get("Contents", [])]
    print("\narquivos:", arquivos)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Baixando um arquivo e virando DataFrame
# MAGIC
# MAGIC O `get_object` devolve um dicionário; o conteúdo está em `Body`, e o `.read()` transforma em bytes. O
# MAGIC pandas espera um arquivo, e o que temos são bytes na memória: o `io.BytesIO` finge ser um arquivo.

# COMMAND ----------

if endpoint:
    import io

    objeto = s3.get_object(Bucket=bucket, Key="vendas.parquet")
    conteudo = objeto["Body"].read()
    print(f"{len(conteudo):,} bytes baixados")

    df_vendas = pd.read_parquet(io.BytesIO(conteudo))
    print(df_vendas.shape)
    display(df_vendas.head())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Escrevendo bytes em arquivo
# MAGIC
# MAGIC No pipeline, o arquivo baixado é guardado **sem nenhuma alteração** no volume (a pasta *landing*). Assim,
# MAGIC se a transformação tiver um bug amanhã, você reprocessa a partir da cópia, sem voltar à origem.
# MAGIC
# MAGIC O `"wb"` do `open` quer dizer *write binary*: escrever bytes, e não texto. O `with` fecha o arquivo
# MAGIC sozinho no fim do bloco, mesmo se der erro no meio.

# COMMAND ----------

pasta_landing = "/Volumes/ecommerce/bronze/arquivos/landing"
dbutils.fs.mkdirs(pasta_landing)


def guardar(conteudo: bytes, nome_arquivo: str) -> str:
    """Grava os bytes recebidos no volume e devolve o caminho."""
    destino = f"{pasta_landing}/{nome_arquivo}"
    with open(destino, "wb") as arquivo:
        arquivo.write(conteudo)
    return destino


if endpoint:
    caminho = guardar(conteudo, "vendas.parquet")
    print("gravado em:", caminho)

    # conferindo: lendo de volta do volume
    df_conferencia = pd.read_parquet(caminho)
    print(df_conferencia.shape)
    display(df_conferencia.head(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Erros comuns neste esquenta
# MAGIC
# MAGIC | Erro | O que aconteceu |
# MAGIC |---|---|
# MAGIC | `IndentationError` | Faltou o recuo de 4 espaços dentro do `for`, do `if` ou da função |
# MAGIC | `NameError: name 'x' is not defined` | A variável não existe: você rodou a célula fora de ordem |
# MAGIC | `KeyError: 'regiao'` | A chave não existe no dicionário; confira a grafia |
# MAGIC | `KeyError: 'Contents'` | O bucket está vazio ou o nome está errado |
# MAGIC | `ModuleNotFoundError` | Biblioteca não instalada: rode `%pip install <nome>` |
# MAGIC | `ConnectionError` ao chamar a API | Conta do Databricks ainda não verificada |
# MAGIC | `EndpointConnectionError` | Endpoint errado; confira o endereço do Storage |
# MAGIC | `InvalidAccessKeyId` / `SignatureDoesNotMatch` | Chave ou segredo errados no secret scope |
# MAGIC
# MAGIC Pronto para o pipeline: siga para o **`01_ingestao_bronze`**.
