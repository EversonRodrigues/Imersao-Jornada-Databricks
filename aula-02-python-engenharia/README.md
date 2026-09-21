# Aula 2: Python & Engenharia de Dados

> **Objetivo do dia:** fazer o dado **chegar sozinho**. Buscar os arquivos em fontes externas, organizar em camadas bronze → silver → gold e agendar tudo para rodar todo dia às 6h.

| | |
|---|---|
| **Material** | 3 notebooks, para rodar em ordem: [`01_ingestao_bronze.py`](./01_ingestao_bronze.py), [`02_silver.py`](./02_silver.py) e [`03_gold.sql`](./03_gold.sql) |
| **Duração** | ~100 minutos |
| **Pré-requisito** | Aula 1 feita (catálogo `ecommerce` criado) e **conta verificada** para acesso à internet |

## Roteiro

| Bloco | Tempo | O que acontece |
|---|---|---|
| Gancho | 5 min | "De onde vieram esses dados?" |
| Teoria | 15 min | ETL, arquitetura medalhão, idempotência, Spark |
| Ingestão | 25 min | Baixar Parquet do data lake e consumir a API do IBGE |
| Bronze | 10 min | Arquivo → tabela Delta com metadados |
| Silver | 20 min | Limpar, tipar, enriquecer e marcar problemas |
| Gold | 15 min | As 3 visões de negócio, com `CASE WHEN` e window functions |
| Job | 10 min | Agendar o pipeline para rodar sozinho |

---

## Parte 1: base teórica

### O problema da Aula 1

Na Aula 1 você baixou 4 CSVs e subiu na mão. Funciona uma vez. Mas numa empresa real:

- chega arquivo novo **todo dia**;
- os dados vêm de **vários lugares** (sistemas, APIs, planilhas, data lakes);
- alguém precisa garantir que o número do dashboard de amanhã está certo **sem ninguém olhar**.

Resolver isso é o trabalho da **engenharia de dados**.

### ETL e ELT

| Sigla | Ordem | Onde transforma |
|---|---|---|
| **ETL** | Extrai → Transforma → Carrega | Fora do destino, antes de gravar |
| **ELT** | Extrai → Carrega → Transforma | Dentro do destino, depois de gravar |

Em um lakehouse, o padrão é **ELT**: primeiro guardamos o dado bruto (é barato e permite reprocessar), depois transformamos com o poder de processamento da própria plataforma. É exatamente o que fazemos hoje.

### Arquitetura medalhão

O dado passa por camadas, e cada uma tem uma responsabilidade:

```
 Fontes ──► BRONZE ──────────► SILVER ─────────────► GOLD
            como chegou        limpo e confiável      pronto para o negócio
            + quando chegou    tipos certos           uma tabela por pergunta
            + de onde veio     sem duplicatas         regras de negócio
                               problemas marcados
```

| Camada | Pergunta que ela responde | Neste projeto |
|---|---|---|
| **Bronze** | "O que exatamente chegou, e quando?" | `bronze.vendas`, `bronze.estados_ibge`... com `_ingerido_em` e `_arquivo_origem` |
| **Silver** | "Posso confiar neste dado?" | Preço em `DECIMAL`, datas convertidas, receita calculada, região do cliente, flag de produto não cadastrado |
| **Gold** | "Qual a resposta para o diretor?" | `vendas_temporais`, `vendas_produtos`, `clientes_segmentacao`, `precos_competitividade` |

**Por que não fazer tudo de uma vez?** Porque, quando algo der errado (e vai dar), você sabe em qual camada procurar, e pode reprocessar a partir da bronze sem voltar à fonte.

### Idempotência

Um pipeline é **idempotente** quando rodá-lo duas vezes dá o mesmo resultado que rodá-lo uma. Isso permite reexecutar sem medo depois de uma falha. Nos notebooks isso aparece como:

- `CREATE ... IF NOT EXISTS` para a estrutura;
- `mode("overwrite")` e `CREATE OR REPLACE TABLE` para os dados.

### Fontes de dados de hoje

**Data lake em Parquet.** O Parquet é um formato de arquivo **colunar**, comprimido e que **guarda os tipos**. Compare:

| | CSV | Parquet |
|---|---|---|
| Legível no bloco de notas | Sim | Não |
| Guarda o tipo de cada coluna | Não (tudo é texto) | Sim |
| Tamanho (`vendas`) | 272 KB | 70 KB |
| Leitura de poucas colunas | Lê o arquivo inteiro | Lê só as colunas pedidas |

**API REST do IBGE.** Uma API é uma porta que um sistema abre para outros pedirem dados. Você faz uma requisição HTTP (`GET` em uma URL) e recebe a resposta em **JSON**, que em Python vira lista e dicionário:

```
GET https://servicodados.ibge.gov.br/api/v1/localidades/estados
→ [{"sigla": "SP", "nome": "São Paulo", "regiao": {"nome": "Sudeste", ...}}, ...]
```

Usamos essa API para responder algo que o nosso cadastro não tem: a **região** de cada cliente, que a Diretora de Customer Success pediu para planejar a equipe regional.

### Spark e PySpark

O **Apache Spark** processa dados distribuindo o trabalho entre várias máquinas. O **PySpark** é o Spark usado a partir do Python. Três ideias para guardar:

1. **DataFrame:** uma tabela em memória, com colunas nomeadas e tipadas. Parecido com o pandas, mas feito para dados que não cabem em uma máquina.
2. **Transformações são preguiçosas (lazy):** `withColumn`, `join` e `filter` só montam um plano. Nada roda até uma **ação** (`count`, `display`, `saveAsTable`).
3. **SQL e PySpark são o mesmo motor:** `spark.sql("SELECT ...")` e `df.groupBy(...)` viram o mesmo plano de execução. Escolha o que deixa o código mais claro.

### Por que PySpark na silver e SQL na gold?

| Camada | Linguagem | Motivo |
|---|---|---|
| Ingestão e bronze | Python | Baixar arquivos, chamar API e repetir para N tabelas com `for` é trabalho de linguagem de programação. |
| Silver | PySpark | Limpeza é uma sequência de passos pequenos. Cada passo vira uma linha que dá para testar e reaproveitar em funções. |
| Gold | SQL | São regras de negócio. O SQL é a língua que o analista e o diretor já leram na Aula 1. |

### Serverless e Jobs

**Serverless** significa que você não gerencia máquinas: o Databricks liga o computador quando o notebook ou o Job começa e desliga quando termina.

Um **Job** é um conjunto de tarefas com ordem de dependência (um **DAG**):

```
ingestao_bronze ──► silver ──► gold
```

Se a `silver` falhar, a `gold` nem começa, e ninguém vê número errado. O Job roda num **agendamento** (expressão cron) e manda e-mail se falhar.

---

## Parte 2: passo a passo

### Antes de começar: acesso à internet

A Free Edition só acessa sites externos com a conta **verificada**. Se a célula de download der erro de conexão (`ConnectionError`, `Max retries exceeded`), verifique a conta pelo LinkedIn quando o Databricks pedir.

**Enquanto a verificação não sai**, dá para seguir a aula: suba os 4 arquivos `.parquet` da pasta [`dados/`](../dados/) para `/Volumes/ecommerce/bronze/arquivos/landing/` pela interface (**Catalog → ecommerce → bronze → arquivos → Upload**) e comece na seção *Bronze* do notebook. A API do IBGE fica para depois da verificação.

### 1. Ingestão → bronze

Abra [`01_ingestao_bronze.py`](./01_ingestao_bronze.py), conecte em **Serverless** e rode célula por célula. No fim, a célula de conferência deve mostrar:

| Tabela | Linhas |
|---|---:|
| `bronze.vendas` | 3.020 |
| `bronze.produtos` | 215 |
| `bronze.clientes` | 50 |
| `bronze.preco_competidores` | 728 |
| `bronze.estados_ibge` | 27 |

> O widget `url_base` aponta para a pasta `dados/` deste repositório no GitHub. Se você fez um fork, troque pelo endereço do seu.

### 2. Silver

Rode [`02_silver.py`](./02_silver.py). Confira:

- `silver.vendas` com **20** linhas `produto_cadastrado = false`;
- clientes por região: Norte 17, Nordeste 12, Centro-Oeste 9, Sudeste 8 e Sul 4;
- `data_coleta` dos concorrentes agora é `timestamp`, e todos os preços são `decimal(10,2)`.

### 3. Gold

Rode [`03_gold.sql`](./03_gold.sql). A última célula faz a **reconciliação**: a receita precisa ser **R$ 974.077,28** em todas as visões.

| Tabela | Resultado esperado |
|---|---|
| `gold.clientes_segmentacao` | 10 VIP, 25 TOP_TIER e 15 REGULAR |
| `gold.precos_competitividade` | 215 produtos: 35 mais caros que todos, 92 acima da média, 6 na média, 76 abaixo da média e 6 mais baratos que todos |
| `gold.vendas_produtos` | Top 1: Fone de Ouvido Esportivo, R$ 116.462,65 |

> **Por que 22 mil e 17 mil na segmentação?** O projeto antigo usava R$ 10 mil e R$ 5 mil. Com esses limites, 49 dos 50 clientes eram VIP, e um segmento que tem todo mundo não ajuda ninguém. Os novos limites vieram da distribuição real (cerca de 20% dos clientes são VIP). Regra de negócio se valida com o dado.

### 4. Agende o Job

1. Menu lateral **Jobs & Pipelines → Create → Job**.
2. Nome: `Pipeline E-commerce`.
3. Primeira tarefa: `ingestao_bronze`, tipo **Notebook**, caminho do `01_ingestao_bronze`, compute **Serverless**.
4. **+ Add task**: `silver`, notebook `02_silver`, *Depends on* `ingestao_bronze`.
5. **+ Add task**: `gold`, notebook `03_gold`, *Depends on* `silver`.
6. Em **Job parameters**, adicione `catalogo` = `ecommerce`.
7. **Schedules & Triggers → Add trigger → Scheduled**: todo dia às 06:00, fuso `America/Sao_Paulo`.
8. Em **Notifications**, coloque seu e-mail para falhas.
9. **Run now** e acompanhe o grafo ficar verde.

> Na Aula 3 este mesmo Job deixa de ser clicado na interface e vira um arquivo YAML versionado no Git: [`resources/pipeline_ecommerce.job.yml`](../resources/pipeline_ecommerce.job.yml).

---

## Erros comuns

| Erro | Causa | Como resolver |
|---|---|---|
| `ConnectionError` / `Max retries exceeded` | Conta não verificada, sem internet | Verifique a conta ou use o upload manual descrito acima |
| `HTTPError: 404` | `url_base` errado | Confira o endereço da pasta `dados/` no GitHub |
| `TABLE_OR_VIEW_NOT_FOUND: silver.vendas` | Rodou a gold antes da silver | Rode os notebooks na ordem |
| `UNBOUND_SQL_PARAMETER: catalogo` | Widget não criado no notebook SQL | Rode a primeira célula (`%python dbutils.widgets.text(...)`) |
| Receita da gold diferente da silver | Algum `JOIN` perdeu ou duplicou vendas | Compare as consultas com o notebook original |

---

## Para praticar

1. Adicione à silver uma coluna `faixa_horaria` (madrugada, manhã, tarde e noite) e leve para a gold.
2. Crie a gold `gold.vendas_por_regiao` juntando `silver.vendas` com `silver.clientes`.
3. Consuma outra API pública (por exemplo, a cotação do dólar em `economia.awesomeapi.com.br`) e grave na bronze.

## Amanhã

O pipeline funciona, mas mora em cliques na interface, sem teste e sem versionamento. Se alguém apagar o Job, ele some. Na [Aula 3](../aula-03-claude-code/) você **profissionaliza** o projeto com Git, testes e deploy, usando IA como par de programação.
