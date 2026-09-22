# Aula 2: Python & Engenharia de Dados

> **Objetivo do dia:** tirar o dado do **data lake** (o Storage do Supabase, que fala o protocolo S3 da AWS) e fazer ele chegar sozinho no Databricks, organizado em bronze → silver → gold, todo dia às 6h.

| | |
|---|---|
| **Esquenta** | [`00_esquenta_python.py`](./00_esquenta_python.py) (exercícios) e [`00_esquenta_python_gabarito.py`](./00_esquenta_python_gabarito.py) |
| **Aula** | [`01_ingestao_bronze.py`](./01_ingestao_bronze.py) → [`02_silver.py`](./02_silver.py) → [`03_gold.sql`](./03_gold.sql) |
| **Duração** | ~110 minutos |
| **Pré-requisito** | Aula 1 feita e **conta verificada** para acesso à internet |

## Roteiro

| Bloco | Tempo | O que acontece |
|---|---|---|
| Esquenta de Python | 20 min | Variáveis, listas, dicionários, `for`, funções, `requests` e `boto3` |
| Teoria | 15 min | Data lake, protocolo S3, ETL, arquitetura medalhão |
| Data lake → bronze | 25 min | Apagar o trabalho manual da Aula 1 e trazer os arquivos do storage |
| Silver | 20 min | Limpar, tipar, enriquecer e marcar problemas |
| Gold | 15 min | As visões de negócio, com `CASE WHEN` e window functions |
| Job | 10 min | Agendar o pipeline para rodar sozinho |

---

## Parte 1: base teórica

### O problema da Aula 1

Você arrastou 4 arquivos CSV e respondeu os diretores. Funciona uma vez. Numa empresa de verdade:

- o dado **não está no seu computador**: está no storage da nuvem, exportado pelos sistemas;
- chega dado novo **o tempo todo**;
- alguém precisa garantir que o número do dashboard de amanhã está certo **sem ninguém olhar**.

Resolver isso é o trabalho da **engenharia de dados**.

### Onde o dado mora numa empresa

O sistema que roda a operação (o e-commerce, o ERP, o CRM) guarda tudo em um banco **transacional**: feito para gravar e ler poucas linhas por vez, muito rápido, milhares de vezes por segundo. Ninguém deixa um analista rodar `GROUP BY` em 10 milhões de linhas ali, porque a consulta pesada competiria com as compras acontecendo no site. É assim que um relatório derruba a loja.

A saída é o **data lake**: os sistemas exportam arquivos para um storage barato na nuvem, e a plataforma analítica lê de lá. Cada um faz o que faz bem.

```
 sistema (banco transacional) ──exporta──► data lake (arquivos) ──lê──► Databricks (análise)
```

### Object storage e o protocolo S3

O **S3** (*Simple Storage Service*) é o serviço de arquivos da AWS, e virou o padrão do mercado: quase todo storage na nuvem hoje aceita o mesmo protocolo, inclusive o **Storage do Supabase**, que é o nosso data lake. O vocabulário é curto:

| Termo | O que é | Aqui |
|---|---|---|
| **Bucket** | A pasta raiz, o "balde" | `ecommerce` |
| **Key** | O caminho do arquivo dentro do bucket | `vendas.parquet` |
| **Endpoint** | O endereço do serviço | `https://<ref>.storage.supabase.co/storage/v1/s3` |
| **Access key / secret** | Usuário e senha da máquina | *Project Settings → Storage → S3 access keys* |

Não é um sistema de arquivos como o do seu computador: não existe "pasta" de verdade, e um arquivo não é alterado no meio. Você grava o objeto inteiro e lê o objeto inteiro. Isso é o que deixa o storage barato e praticamente infinito.

### boto3: a biblioteca de S3

```python
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="https://<ref>.storage.supabase.co/storage/v1/s3",
    region_name="us-east-2",
    aws_access_key_id=dbutils.secrets.get("imersao", "s3_key"),
    aws_secret_access_key=dbutils.secrets.get("imersao", "s3_secret"),
)

s3.list_objects_v2(Bucket="ecommerce")            # o que existe no bucket
s3.get_object(Bucket="ecommerce", Key="vendas.parquet")   # baixar um arquivo
```

O `boto3` é da AWS, mas o `endpoint_url` faz ele falar com qualquer storage compatível. O código que você escreve hoje funciona igual na Amazon.

### Credencial não vai no notebook

Notebook vai para o Git, e credencial em repositório é incidente de segurança. Guarde no **secret scope** do Databricks:

```bash
databricks secrets create-scope imersao
databricks secrets put-secret imersao s3_key
databricks secrets put-secret imersao s3_secret
```

No notebook, `dbutils.secrets.get("imersao", "s3_key")` lê o valor, e o Databricks troca o segredo por `[REDACTED]` em qualquer saída impressa.

### ETL e ELT

| Sigla | Ordem | Onde transforma |
|---|---|---|
| **ETL** | Extrai → Transforma → Carrega | Fora do destino, antes de gravar |
| **ELT** | Extrai → Carrega → Transforma | Dentro do destino, depois de gravar |

Em um lakehouse o padrão é **ELT**: primeiro guardamos o dado bruto (é barato e permite reprocessar), depois transformamos com o poder da própria plataforma.

### Arquitetura medalhão

```
 Origem ──► BRONZE ──────────► SILVER ─────────────► GOLD
 data lake  como chegou        limpo e confiável      pronto para o negócio
 + API      + quando chegou    tipos certos           uma tabela por pergunta
            + de onde veio     sem duplicatas         regras de negócio
                               problemas marcados
```

| Camada | Pergunta que ela responde | Neste projeto |
|---|---|---|
| **Bronze** | "O que exatamente chegou, e quando?" | `bronze.vendas`, `bronze.estados_ibge`… com `_ingerido_em` e `_origem` |
| **Silver** | "Posso confiar neste dado?" | Preço em `DECIMAL`, datas convertidas, receita calculada, região do cliente, flag de produto não cadastrado |
| **Gold** | "Qual a resposta para o diretor?" | `vendas_temporais`, `vendas_produtos`, `clientes_segmentacao`, `precos_competitividade` |

**Por que não fazer tudo de uma vez?** Porque, quando algo der errado (e vai dar), você sabe em qual camada procurar e reprocessa a partir da bronze, sem precisar baixar tudo da origem de novo.

### Idempotência

Um pipeline é **idempotente** quando rodá-lo duas vezes dá o mesmo resultado que rodá-lo uma. Isso permite reexecutar sem medo depois de uma falha. No código isso aparece como `CREATE ... IF NOT EXISTS` para a estrutura e `mode("overwrite")` para os dados.

### Por que guardar uma cópia em Parquet

Os arquivos do data lake já são **Parquet**: formato colunar, comprimido e que guarda os tipos. Antes de transformar, o pipeline copia cada um para o volume, sem alterar nada.

| | CSV | Parquet |
|---|---|---|
| Guarda o tipo de cada coluna | Não (tudo é texto) | Sim |
| Tamanho (`vendas`) | 272 KB | 70 KB |
| Leitura de poucas colunas | Lê o arquivo inteiro | Lê só as colunas pedidas |

Com essa cópia no volume, reprocessar não exige baixar tudo de novo da origem.

### Spark e PySpark

O **Apache Spark** processa dados distribuindo o trabalho entre várias máquinas; o **PySpark** é o Spark a partir do Python. Três ideias:

1. **DataFrame:** uma tabela com colunas nomeadas e tipadas. Parecido com o pandas, mas feito para dados que não cabem em uma máquina.
2. **Transformações são preguiçosas:** `withColumn`, `join` e `filter` só montam um plano; nada roda até uma **ação** (`count`, `display`, `saveAsTable`).
3. **SQL e PySpark são o mesmo motor:** escolha o que deixa o código mais claro.

> **pandas ou PySpark?** O pandas trabalha na memória de uma máquina e é ótimo para inspecionar o arquivo que acabou de chegar. O PySpark escala para bilhões. Aqui usamos pandas na ingestão e PySpark da bronze em diante, que é o caminho natural quando o volume cresce.

### Serverless e Jobs

**Serverless** significa que você não gerencia máquinas. Um **Job** é um conjunto de tarefas com ordem de dependência (um **DAG**):

```
ingestao_bronze ──► silver ──► gold
```

Se a silver falhar, a gold nem começa, e ninguém vê número errado. O Job roda em um agendamento (expressão cron) e manda e-mail se falhar.

---

## Parte 2: passo a passo

### 0. Antes de começar

**Acesso à internet.** A Free Edition só acessa serviços externos com a conta **verificada**. Se a conexão falhar (`ConnectionError`, `Max retries exceeded`), verifique a conta pelo LinkedIn quando o Databricks pedir.

**O data lake.** Você precisa de um bucket com os 4 arquivos Parquet (`vendas`, `produtos`, `clientes` e `preco_competidores`), que estão na pasta [`dados/`](../dados/). No Supabase:

1. **Storage → New bucket**, nome `ecommerce`.
2. Faça upload dos 4 arquivos `.parquet`.
3. **Project Settings → Storage → S3 access keys → New access key**. Guarde as duas partes.
4. Anote o endpoint, que aparece na mesma tela: `https://<ref>.storage.supabase.co/storage/v1/s3`.
5. Guarde as chaves no Databricks:
   ```bash
   databricks secrets create-scope imersao
   databricks secrets put-secret imersao s3_key
   databricks secrets put-secret imersao s3_secret
   ```

> **Plano B:** se o storage não estiver pronto (ou cair no meio da aula), mude o widget `origem` para `arquivos`. O notebook passa a baixar os mesmos Parquet do repositório, e a aula continua sem interrupção.

### 1. Esquenta de Python (20 min)

Abra [`00_esquenta_python.py`](./00_esquenta_python.py) e resolva os 10 exercícios: variáveis, listas, dicionários, `for`, `if`, funções, `requests` com a API do IBGE, pandas, `boto3` no Storage do Supabase e escrita de arquivos no volume. As respostas comentadas estão no [gabarito](./00_esquenta_python_gabarito.py).

### 2. Data lake → bronze

Abra [`01_ingestao_bronze.py`](./01_ingestao_bronze.py), conecte em **Serverless** e rode célula por célula.

O notebook começa **apagando** as tabelas que você subiu na mão na Aula 1. É proposital: no fim, elas voltam vindas do data lake, com a marca de quando e de onde chegaram.

No fim, a conferência deve mostrar:

| Tabela | Linhas |
|---|---:|
| `bronze.vendas` | 3.020 |
| `bronze.produtos` | 215 |
| `bronze.clientes` | 50 |
| `bronze.preco_competidores` | 728 |
| `bronze.estados_ibge` | 27 |

### 3. Silver

Rode [`02_silver.py`](./02_silver.py). Confira:

- `silver.vendas` com **20** linhas `produto_cadastrado = false`;
- clientes por região: Norte 17, Nordeste 12, Centro-Oeste 9, Sudeste 8 e Sul 4;
- `data_coleta` agora é `timestamp` e todos os preços são `decimal(10,2)`.

### 4. Gold

Rode [`03_gold.sql`](./03_gold.sql). A última célula faz a **reconciliação**: a receita precisa ser **R$ 974.077,28** em todas as visões.

| Tabela | Resultado esperado |
|---|---|
| `gold.clientes_segmentacao` | 10 VIP, 25 TOP_TIER e 15 REGULAR |
| `gold.precos_competitividade` | 215 produtos: 35 mais caros que todos, 92 acima da média, 6 na média, 76 abaixo da média e 6 mais baratos que todos |
| `gold.vendas_produtos` | Top 1: Fone de Ouvido Esportivo, R$ 116.462,65 |

> **Por que 22 mil e 17 mil na segmentação?** O projeto antigo usava R$ 10 mil e R$ 5 mil. Com esses limites, 49 dos 50 clientes eram VIP, e um segmento que tem todo mundo não ajuda ninguém. Os novos limites vieram da distribuição real: cerca de 20% dos clientes são VIP. Regra de negócio se valida com o dado.

### 5. Agende o Job

1. **Jobs & Pipelines → Create → Job**, nome `Pipeline E-commerce`.
2. Tarefa `ingestao_bronze`: notebook `01_ingestao_bronze`, compute **Serverless**.
3. **+ Add task** `silver` (notebook `02_silver`), dependendo de `ingestao_bronze`.
4. **+ Add task** `gold` (notebook `03_gold`), dependendo de `silver`.
5. Em **Job parameters**: `catalogo` = `ecommerce`, `origem` = `supabase`, `s3_endpoint`, `s3_bucket` e `s3_region`.
6. **Schedules & Triggers → Scheduled**: todo dia às 06:00, fuso `America/Sao_Paulo`.
7. Em **Notifications**, coloque seu e-mail para falhas.
8. **Run now** e acompanhe o grafo ficar verde.

> Na Aula 3 este mesmo Job deixa de ser clicado na interface e vira um arquivo versionado no Git: [`resources/pipeline_ecommerce.job.yml`](../resources/pipeline_ecommerce.job.yml).

---

## Erros comuns

| Erro | Causa | Como resolver |
|---|---|---|
| `EndpointConnectionError` | Endpoint errado ou sem internet | Confira o endereço do Storage e a verificação da conta |
| `InvalidAccessKeyId` / `SignatureDoesNotMatch` | Chave ou segredo errados | Recrie a chave no Supabase e atualize o secret scope |
| `NoSuchBucket` | Nome do bucket errado | Confira o widget `s3_bucket` |
| `KeyError: 'Contents'` | Bucket vazio | Faça o upload dos 4 Parquet |
| `NoSuchKey` | Nome do arquivo diferente | Os arquivos precisam se chamar `vendas.parquet`, `produtos.parquet`… |
| `ValueError: Preencha o widget s3_endpoint` | Widget vazio | Preencha o endpoint ou use `origem = arquivos` |
| `ConnectionError` na API do IBGE | Conta não verificada | Verifique pelo LinkedIn; enquanto isso, use `origem = arquivos` |
| `TABLE_OR_VIEW_NOT_FOUND: silver.vendas` | Rodou a gold antes da silver | Rode os notebooks na ordem |
| Receita da gold diferente da silver | Algum `JOIN` perdeu ou duplicou vendas | Compare com as consultas originais |

---

## Para praticar

1. Baixe só os arquivos que mudaram desde a última execução, comparando o `LastModified` que o `list_objects_v2` devolve. É o começo da **carga incremental**.
2. Acrescente à silver uma coluna `faixa_horaria` (madrugada, manhã, tarde e noite) e leve para a gold.
3. Consuma outra API pública (por exemplo, a cotação do dólar em `economia.awesomeapi.com.br`) e grave na bronze.
4. Use o `put_object` do `boto3` para devolver ao bucket um arquivo gerado por você, por exemplo a gold em Parquet.

## Amanhã

O pipeline funciona, mas mora em cliques na interface, sem teste e sem versionamento. Se alguém apagar o Job, ele some. Na [Aula 3](../aula-03-claude-code/) você **profissionaliza** o projeto com Git, testes e deploy, usando IA como par de programação.
