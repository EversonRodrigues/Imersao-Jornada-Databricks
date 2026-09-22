# Aula 2: Python & Engenharia de Dados

> **Objetivo do dia:** tirar o dado do **banco de produção** (Postgres no Supabase, rodando na AWS) e fazer ele chegar sozinho no Databricks, organizado em bronze → silver → gold, todo dia às 6h.

| | |
|---|---|
| **Esquenta** | [`00_esquenta_python.py`](./00_esquenta_python.py) (exercícios) e [`00_esquenta_python_gabarito.py`](./00_esquenta_python_gabarito.py) |
| **Aula** | [`01_ingestao_bronze.py`](./01_ingestao_bronze.py) → [`02_silver.py`](./02_silver.py) → [`03_gold.sql`](./03_gold.sql) |
| **Duração** | ~110 minutos |
| **Pré-requisito** | Aula 1 feita e **conta verificada** para acesso à internet |

## Roteiro

| Bloco | Tempo | O que acontece |
|---|---|---|
| Esquenta de Python | 20 min | Variáveis, listas, dicionários, `for`, funções, `requests`, `boto3`, SQLAlchemy |
| Teoria | 15 min | Banco transacional × analítico, ETL, medalhão, pooler de conexão |
| Supabase → bronze | 25 min | Apagar o trabalho manual da Aula 1 e trazer o dado do banco |
| Silver | 20 min | Limpar, tipar, enriquecer e marcar problemas |
| Gold | 15 min | As visões de negócio, com `CASE WHEN` e window functions |
| Job | 10 min | Agendar o pipeline para rodar sozinho |

---

## Parte 1: base teórica

### O problema da Aula 1

Você arrastou 4 arquivos CSV e respondeu os diretores. Funciona uma vez. Numa empresa de verdade:

- o dado **não está em CSV**: está no banco do sistema que roda a operação;
- chega dado novo **o tempo todo**;
- alguém precisa garantir que o número do dashboard de amanhã está certo **sem ninguém olhar**.

Resolver isso é o trabalho da **engenharia de dados**.

### Banco transacional × banco analítico

O e-commerce roda em um **Postgres** hospedado no Supabase. É um banco **transacional** (OLTP): feito para gravar e ler poucas linhas por vez, muito rápido, milhares de vezes por segundo.

| | Transacional (OLTP) · Postgres | Analítico (OLAP) · Databricks |
|---|---|---|
| Pergunta típica | "Qual o pedido 8f3a?" | "Qual a receita por categoria nos últimos 30 dias?" |
| Lê | Poucas linhas, muitas vezes | Milhões de linhas, poucas vezes |
| Organização | Por linha | Por coluna |
| Otimizado para | Velocidade de gravação | Velocidade de agregação |

**Por que não deixar o diretor consultar o Postgres direto?** Porque uma consulta analítica pesada (um `GROUP BY` em 10 milhões de linhas) compete com as compras acontecendo no site. É assim que um relatório derruba a loja. Por isso copiamos o dado para a plataforma analítica: cada um faz o que faz bem.

### ETL e ELT

| Sigla | Ordem | Onde transforma |
|---|---|---|
| **ETL** | Extrai → Transforma → Carrega | Fora do destino, antes de gravar |
| **ELT** | Extrai → Carrega → Transforma | Dentro do destino, depois de gravar |

Em um lakehouse o padrão é **ELT**: primeiro guardamos o dado bruto (é barato e permite reprocessar), depois transformamos com o poder da própria plataforma.

### Arquitetura medalhão

```
 Origem ──► BRONZE ──────────► SILVER ─────────────► GOLD
 Postgres   como chegou        limpo e confiável      pronto para o negócio
 + API      + quando chegou    tipos certos           uma tabela por pergunta
            + de onde veio     sem duplicatas         regras de negócio
                               problemas marcados
```

| Camada | Pergunta que ela responde | Neste projeto |
|---|---|---|
| **Bronze** | "O que exatamente chegou, e quando?" | `bronze.vendas`, `bronze.estados_ibge`… com `_ingerido_em` e `_origem` |
| **Silver** | "Posso confiar neste dado?" | Preço em `DECIMAL`, datas convertidas, receita calculada, região do cliente, flag de produto não cadastrado |
| **Gold** | "Qual a resposta para o diretor?" | `vendas_temporais`, `vendas_produtos`, `clientes_segmentacao`, `precos_competitividade` |

**Por que não fazer tudo de uma vez?** Porque, quando algo der errado (e vai dar), você sabe em qual camada procurar e reprocessa a partir da bronze, sem voltar a incomodar o banco de produção.

### Idempotência

Um pipeline é **idempotente** quando rodá-lo duas vezes dá o mesmo resultado que rodá-lo uma. Isso permite reexecutar sem medo depois de uma falha. No código isso aparece como `CREATE ... IF NOT EXISTS` para a estrutura e `mode("overwrite")` para os dados.

### Como o Python conversa com o Postgres

Três peças, nesta ordem:

| Peça | Papel |
|---|---|
| **Driver** (`psycopg2`) | Fala a língua do Postgres |
| **SQLAlchemy** (`create_engine`) | Cria a conexão reutilizável, a *engine* |
| **pandas** (`read_sql`) | Executa o SQL pela engine e devolve um DataFrame |

```python
from sqlalchemy import create_engine
import pandas as pd

engine = create_engine(uri, pool_pre_ping=True)
df = pd.read_sql("SELECT * FROM vendas", engine)
```

### Os três modos de conexão do Supabase

Na tela **Connect** do Supabase aparecem três opções. A escolha não é detalhe:

| Modo | Porta | Quando usar |
|---|---|---|
| **Session pooler** | 5432 | **O nosso caso.** Funciona em rede IPv4, que é a do Databricks serverless, e se dá bem com o driver do Postgres |
| Transaction pooler | 6543 | Funções serverless de vida muito curta; pode atrapalhar drivers que usam *prepared statements* |
| Direct connection | 5432 | Servidor fixo com IPv6, ou com o add-on pago de IPv4 |

Um **pooler** é um porteiro de conexões: em vez de cada cliente abrir uma conexão nova com o banco (caro), ele mantém um conjunto de conexões prontas e empresta. Sem isso, um punhado de processos derruba um Postgres pequeno.

A URI do Session pooler:

```
postgresql+psycopg2://postgres.<ref>:<senha>@aws-0-<regiao>.pooler.supabase.com:5432/postgres?sslmode=require
```

### Senha não vai no notebook

Notebook vai para o Git, e senha em repositório é incidente de segurança. Guarde no **secret scope** do Databricks:

```bash
databricks secrets create-scope imersao
databricks secrets put-secret imersao supabase_uri
```

No notebook, `dbutils.secrets.get("imersao", "supabase_uri")` lê o valor, e o Databricks troca o segredo por `[REDACTED]` em qualquer saída impressa.

### Por que guardar uma cópia em Parquet

Antes de transformar, o pipeline grava no volume uma cópia fiel do que veio do banco, em **Parquet**: formato colunar, comprimido e que guarda os tipos.

| | CSV | Parquet |
|---|---|---|
| Guarda o tipo de cada coluna | Não (tudo é texto) | Sim |
| Tamanho (`vendas`) | 272 KB | 70 KB |
| Leitura de poucas colunas | Lê o arquivo inteiro | Lê só as colunas pedidas |

Com essa cópia, reprocessar não exige tocar de novo no banco de produção.

### Spark e PySpark

O **Apache Spark** processa dados distribuindo o trabalho entre várias máquinas; o **PySpark** é o Spark a partir do Python. Três ideias:

1. **DataFrame:** uma tabela com colunas nomeadas e tipadas. Parecido com o pandas, mas feito para dados que não cabem em uma máquina.
2. **Transformações são preguiçosas:** `withColumn`, `join` e `filter` só montam um plano; nada roda até uma **ação** (`count`, `display`, `saveAsTable`).
3. **SQL e PySpark são o mesmo motor:** escolha o que deixa o código mais claro.

> **pandas ou PySpark?** O pandas trabalha na memória de uma máquina e é ótimo para os milhares de linhas que vêm do Postgres. O PySpark escala para bilhões. Aqui usamos pandas na ingestão e PySpark da bronze em diante, que é o caminho natural quando o volume cresce.

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

**O banco de origem.** Você precisa de um Postgres com as 4 tabelas (`vendas`, `produtos`, `clientes`, `preco_competidores`). No Supabase:

1. Crie um projeto (ou use um existente) e anote a senha do banco.
2. Carregue os dados da pasta [`dados/`](../dados/) nas 4 tabelas (pelo **Table Editor → Import data from CSV**).
3. Em **Connect**, copie a URI do **Session pooler** e troque `[YOUR-PASSWORD]` pela senha real.
4. Guarde a URI no segredo do Databricks:
   ```bash
   databricks secrets create-scope imersao
   databricks secrets put-secret imersao supabase_uri
   ```

> **Plano B:** se o banco não estiver pronto (ou cair no meio da aula), mude o widget `origem` para `arquivos`. O notebook passa a ler os mesmos dados em Parquet, direto do repositório, e a aula continua sem interrupção.

### 1. Esquenta de Python (20 min)

Abra [`00_esquenta_python.py`](./00_esquenta_python.py) e resolva os 10 exercícios: variáveis, listas, dicionários, `for`, `if`, funções, `requests` com a API do IBGE, pandas, `boto3` no Storage do Supabase e SQLAlchemy. As respostas comentadas estão no [gabarito](./00_esquenta_python_gabarito.py).

### 2. Supabase → bronze

Abra [`01_ingestao_bronze.py`](./01_ingestao_bronze.py), conecte em **Serverless** e rode célula por célula.

O notebook começa **apagando** as tabelas que você subiu na mão na Aula 1. É proposital: no fim, elas voltam vindas do banco, com a marca de quando e de onde chegaram.

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
5. Em **Job parameters**: `catalogo` = `ecommerce` e `origem` = `supabase`.
6. **Schedules & Triggers → Scheduled**: todo dia às 06:00, fuso `America/Sao_Paulo`.
7. Em **Notifications**, coloque seu e-mail para falhas.
8. **Run now** e acompanhe o grafo ficar verde.

> Na Aula 3 este mesmo Job deixa de ser clicado na interface e vira um arquivo versionado no Git: [`resources/pipeline_ecommerce.job.yml`](../resources/pipeline_ecommerce.job.yml).

---

## Erros comuns

| Erro | Causa | Como resolver |
|---|---|---|
| `OperationalError: could not translate host name` | URI errada ou incompleta | Copie de novo em **Connect → Session pooler** |
| `OperationalError: connection timed out` | Modo **Direct connection** em rede IPv4 | Use o **Session pooler** |
| `FATAL: password authentication failed` | Senha errada na URI | O usuário do pooler é `postgres.<ref>`, e não `postgres` |
| `ModuleNotFoundError: psycopg2` | Faltou instalar o driver | Rode a célula `%pip install sqlalchemy psycopg2-binary` |
| `ValueError: Sem URI do Supabase` | Widget e segredo vazios | Preencha o widget ou crie o segredo `imersao/supabase_uri` |
| `ConnectionError` na API do IBGE | Conta não verificada | Verifique pelo LinkedIn; enquanto isso, use `origem = arquivos` |
| `TABLE_OR_VIEW_NOT_FOUND: silver.vendas` | Rodou a gold antes da silver | Rode os notebooks na ordem |
| Receita da gold diferente da silver | Algum `JOIN` perdeu ou duplicou vendas | Compare com as consultas originais |

---

## Para praticar

1. Leia do Postgres só as vendas dos últimos 7 dias, em vez da tabela inteira (`WHERE data_venda >= ...`). É o começo da **carga incremental**.
2. Acrescente à silver uma coluna `faixa_horaria` (madrugada, manhã, tarde e noite) e leve para a gold.
3. Consuma outra API pública (por exemplo, a cotação do dólar em `economia.awesomeapi.com.br`) e grave na bronze.
4. Use o `boto3` do esquenta para ler um arquivo do Storage do Supabase e gravá-lo na bronze.

## Amanhã

O pipeline funciona, mas mora em cliques na interface, sem teste e sem versionamento. Se alguém apagar o Job, ele some. Na [Aula 3](../aula-03-claude-code/) você **profissionaliza** o projeto com Git, testes e deploy, usando IA como par de programação.
