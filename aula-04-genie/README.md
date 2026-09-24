# Aula 4: Dashboards e Genie

> **Objetivo do dia:** transformar a gold da Aula 3 em produto para os três diretores. Um **dashboard para cada diretoria** e um **agente do Genie** que responde em português, direto da gold, testado com perguntas de resposta conhecida antes de chegar ao diretor.
>
> **No dia 1 você respondeu o diretor. No dia 4 ele não precisa mais de você para perguntar.**

| | |
|---|---|
| **Prompts** | [`prompts/`](./prompts/): a Aula 4 inteira em 2 prompts (`prompt_01.md` e `prompt_02.md`) |
| **Gabarito** | [`dashboards/`](./dashboards/) (os 3 dashboards) e [`genie/diretoria_ecommerce.geniespace.json`](./genie/diretoria_ecommerce.geniespace.json) (o agente) |
| **Guia** | [`GUIA_DASHBOARDS_E_GENIE.md`](./GUIA_DASHBOARDS_E_GENIE.md): como funcionam os dashboards AI/BI e o Genie no Databricks |
| **Apoio** | [`01_preparar_dados_para_ia.sql`](./01_preparar_dados_para_ia.sql) (o que o Genie enxerga da gold) e [`perguntas_demo.md`](./perguntas_demo.md) (as perguntas com a resposta conferida) |
| **Duração** | ~95 minutos |
| **Pré-requisito** | Aula 3 feita: projeto com as 5 golds e o Job verde; Claude Code com o plugin Databricks |

### Aula 3 × Aula 4: qual a diferença?

| | Aula 3 | Aula 4 |
|---|---|---|
| O que entrega | O dado certo: silver e gold testadas | O dado **usado**: dashboards e Genie |
| Para quem | Para o time de dados | Para os diretores |
| O que o Claude Code escreve | Pipeline, expectations, testes e Job | Dashboards em JSON e o Genie space, como código no mesmo bundle |
| Como sei que está certo | Testes entre tabelas | KPIs conferidos contra SQL e 10 perguntas com resposta conhecida |

## Roteiro

| Bloco | Tempo | O que acontece |
|---|---|---|
| Recap | 10 min | A gold pronta: 5 tabelas, comentários em todas as colunas, números que batem |
| Teoria | 15 min | Dashboard × Genie, como o Genie funciona e por que a IA erra com dado bagunçado |
| Prompt 1 | 25 min | Três dashboards, um por diretoria, com deploy e conferência dos KPIs |
| Prompt 2 | 35 min | O agente do Genie: instruções, joins, SQL de exemplo e as 12 perguntas de teste |
| Entrega | 10 min | Botão **Ask Genie** nos dashboards e compartilhamento com os diretores |

---

## Parte 1: base teórica

### Todo mundo quer IA. Ninguém tem o dado organizado.

A maior parte dos projetos de "IA para dados" falha pelo mesmo motivo: a IA recebe tabelas com nomes crípticos, colunas sem descrição, regras de negócio que só existem na cabeça de alguém, e é obrigada a adivinhar. Você passou três dias fazendo o contrário: dado limpo, uma tabela por pergunta de negócio, regras escritas e testadas, comentário em toda coluna gold. **É por isso que o dashboard sai certo e o Genie acerta.**

### Dashboard × Genie: os dois se completam

| | Dashboard (prompt 1) | Genie (prompt 2) |
|---|---|---|
| Pergunta | Definida por quem montou | Livre, do usuário, em português |
| Melhor para | Acompanhar os mesmos números todo dia | Perguntas novas, exploração |
| Risco | Não responder o que ninguém previu | Responder errado com confiança |
| Controle | Total | Depende do contexto que você deu ao space |

Um dashboard por diretoria, e não um dashboard com tudo: cada diretor abre a página dele e vê primeiro os 3 ou 4 números que acompanha. O botão **Ask Genie** leva do gráfico para a conversa, quando surge a pergunta que o dashboard não previu.

### Como o Genie funciona

O Genie é um agente de *text-to-SQL*: transforma a pergunta em SQL, executa no SQL warehouse e explica o resultado.

```
"Quantos clientes VIP temos?"
        │
        ▼
 1. Lê o contexto do space ──► tabelas, comentários, instruções, joins, exemplos
 2. Um modelo de linguagem escreve o SQL
 3. O SQL roda no warehouse, com as SUAS permissões do Unity Catalog
 4. Devolve tabela, gráfico e um resumo em português
        │
        ▼
"10 clientes VIP, que representam 27,0% da receita."
```

- **O Genie não "sabe" nada sobre a sua empresa.** Tudo o que ele sabe vem do que você coloca no space.
- **O SQL fica visível.** Todo resultado tem o botão **Show code**. Isso é o que permite confiar (ou desconfiar) da resposta.
- **As permissões continuam valendo.** Quem não pode ver uma tabela no Unity Catalog também não vê pelo Genie.

### O que faz o Genie acertar

| Camada de contexto | O que é | Neste projeto |
|---|---|---|
| **Tabelas certas** | Poucas tabelas, cada uma com um propósito | As 5 golds, e nenhuma da bronze ou da silver |
| **Comentários** | Descrição de cada tabela e coluna no Unity Catalog | `receita`: "Receita bruta em reais (R$) = quantidade × preço unitário" |
| **Instruções** | Regra de negócio que não cabe numa coluna | "Não existe lucro nos dados"; "o período vai de 13/12/2025 a 11/01/2026" |
| **Joins** | Como as tabelas se relacionam | `vendas_produtos.id_produto = precos_competitividade.id_produto` |
| **SQL de exemplo** | Pares pergunta → SQL certo | Ticket médio sem cair na média de médias |
| **Sinônimos** | Palavras do negócio que apontam para uma coluna | "faturamento" → `receita`; "UF" → `estado` |

A ordem importa: **comentário bom resolve mais que instrução longa.** Os comentários já foram escritos na Aula 3, na definição de cada materialized view; o prompt 2 só acrescenta o que não cabe neles.

### Os erros clássicos de text-to-SQL (e como este projeto evita cada um)

| Erro | Exemplo | Como evitamos |
|---|---|---|
| Somar o que não se soma | Somar `clientes_unicos` de vários dias | Comentário da coluna: "Não somar entre linhas" |
| Usar a data de hoje | "Vendas de ontem" com `current_date()` | Instrução: os dados terminam em 11/01/2026 |
| Contar pelo nome | Produtos diferentes com o mesmo nome | Instrução: contar por `id_produto` |
| Média de médias | Ticket médio = `AVG(ticket_medio)` | SQL de exemplo com `SUM(receita) / SUM(total_vendas)` |
| Inventar métrica | "Qual o lucro?" | Instrução: só existe receita |
| Comparar totais desiguais | Sábado "vende mais" porque o período tem 5 sábados | Instrução: comparar pela receita média por dia |
| Reagir a dado suspeito | "Tênis está 100% mais caro" | Instrução e dashboard separam o preço confirmado do preço a conferir |

### A armadilha do Tênis (o que o teste dos prompts revelou)

A gold diz que **35 produtos** estão mais caros que todos os concorrentes. Quando o Claude Code cruzou a classificação com `possui_preco_suspeito`, apareceu o detalhe: **15 desses 35 são Tênis** cujo preço de concorrente é exatamente a metade do nosso, e nenhum deles vendeu. A média da categoria Tênis sai "+100% acima do mercado", mas é erro de coleta (ou promoção), não preço real.

- Confirmados: **20 produtos**, com R$ 161.375,09 de receita.
- Sem os suspeitos, a categoria mais cara é Beleza, com só +1,24%. Não há problema de preço generalizado.
- A ação para o Tênis é **conferir a coleta**, não baixar o preço.

Por isso o dashboard de Pricing separa o confirmado do "a conferir", e o Genie foi instruído a avisar quando a resposta inclui preço suspeito. É a lição da Aula 3 (marcar, medir e não apagar) chegando ao diretor.

---

## Parte 2: passo a passo

### 1. Confira o que o Genie vai enxergar

Abra [`01_preparar_dados_para_ia.sql`](./01_preparar_dados_para_ia.sql) e rode (troque o widget `catalogo` para o seu). Ele lista o comentário de cada tabela e coluna gold e confirma que nenhuma coluna está sem descrição.

### 2. Prompt 1: um dashboard para cada diretor

Copie a pasta [`prompts/`](./prompts/) desta aula para dentro do projeto da Aula 3 (renomeie para `prompts_aula4/`, para não misturar com os prompts da Aula 3). No Claude Code:

```text
Execute o que está em @prompts_aula4/prompt_01.md
```

O Claude Code explora a gold, testa cada consulta no warehouse, escreve os 3 dashboards como JSON dentro do bundle, faz o deploy em `dev` e confere os KPIs contra SQL direto na gold.

| Dashboard | KPIs | Gráficos e tabela | Filtros |
|---|---|---|---|
| **Diretoria Comercial** | Receita, vendas, ticket médio, itens | Receita por dia e canal, por canal, média por dia da semana, por hora, por categoria; top 10 produtos | Período e canal |
| **Diretoria de Customer Success** | Clientes, VIPs, % da receita VIP, ticket médio | Clientes e receita por segmento, receita por região; ranking de clientes | Segmento e região |
| **Diretoria de Pricing** | Produtos monitorados, mais caros que todos (confirmados), receita deles, preços a conferir | Classificação de preço, diferença por categoria; tabela de ação | Categoria e classificação |

**Revise antes de seguir:** abra cada dashboard, confira os KPIs com a Parte 3 e mexa nos filtros. Leia a conclusão que o Claude Code dá para o diretor de Pricing.

### 3. Prompt 2: o agente do Genie

```text
Execute o que está em @prompts_aula4/prompt_02.md
```

O Claude Code cria o Genie space **Diretoria E-commerce** como código (`src/genie/` + `resources/diretoria.genie_space.yml`), com:
- as 5 tabelas gold;
- instruções curtas, só com regra de negócio (período, lucro inexistente, ticket médio, segmentos, preço suspeito, dia da semana pela média);
- joins entre `vendas_produtos` × `precos_competitividade` e `vendas_detalhadas` × `clientes_segmentacao`;
- SQL de exemplo para as contas em que a IA costuma errar;
- sinônimos e 6 perguntas de exemplo, duas por diretoria.

Depois ele **testa o space pela API de conversa do Genie**: faz as 10 perguntas de [`perguntas_demo.md`](./perguntas_demo.md) e as 2 de limite, compara cada resposta com SQL direto na gold e, se o Genie errar, melhora o contexto e pergunta de novo. No fim, liga o botão **Ask Genie** dos 3 dashboards ao space.

> **Mudou uma instrução?** Edite o JSON e faça deploy. Ajuste feito pela interface se perde no próximo `bundle deploy`.

### 4. Pergunte você mesmo

Abra o space e faça as perguntas de [`perguntas_demo.md`](./perguntas_demo.md). Para cada resposta, clique em **Show code** e leia o SQL com a turma. Esse hábito é o que separa quem usa IA de quem é enganado por ela. Termine com as perguntas de limite: "Qual foi o nosso lucro?" e "Quanto vendemos ontem?".

### 5. Compartilhe com os diretores

- **Genie:** **Share** → adicione as pessoas com **Can run**.
- **Dashboards:** **Share** → **Can view**, pelo link publicado.
- Elas também precisam de `SELECT` nas tabelas gold e de acesso ao warehouse.

### Atalho: o gabarito deste repositório

Os 3 dashboards e o Genie do gabarito estão no bundle da raiz, lendo do catálogo `ecommerce`:

```bash
databricks bundle deploy -t dev -p <perfil>
databricks bundle summary -t dev -p <perfil>    # links dos dashboards e do Genie
```

---

## Parte 3: resultados esperados

**Dashboards** (conferidos contra SQL direto na gold):

| Dashboard | Número | Esperado |
|---|---|---|
| Comercial | Receita / vendas / ticket médio | R$ 974.077,28 / 3.020 / R$ 322,54 |
| Comercial | E-commerce | 2.155 vendas, R$ 705.486,21 |
| Customer Success | Clientes / VIP | 50 / 10 VIP com 27,0% da receita |
| Customer Success | Região de maior receita | Norte, R$ 333.078,69 (17 clientes) |
| Pricing | Produtos monitorados | 215 |
| Pricing | Mais caros que todos | 35: 20 confirmados (R$ 161.375,09) e 15 Tênis a conferir |
| Pricing | Categoria mais cara, sem suspeitos | Beleza, +1,24% |

**Genie:** 10 de 10 perguntas certas e as 2 de limite recusadas sem inventar. No teste dos prompts, o placar foi evoluindo assim:

| Rodada | Placar | O que o Claude Code mudou no space |
|---|---|---|
| 1 | 7/10 e 1/2 | Vendas sem ticket, região sem nº de clientes, "35 mais caros" sem separar os suspeitos, e "ontem" respondido como 10/01/2026 |
| 2 | 9/10 e 2/2 | Instruções: trazer a quantidade junto da receita, separar preço suspeito, não responder "hoje/ontem" |
| 3 | 10/10 e 2/2 | Instrução: citar o número de clientes em perguntas por região, estado ou segmento |

Essa evolução é o ponto da aula: o Genie errou do jeito que um analista novo erraria, e cada erro virou uma regra escrita. As regras dessas rodadas já estão no [prompt 2](./prompts/prompt_02.md), então no seu projeto o Genie tende a acertar mais cedo.

Uma segunda execução do prompt, num projeto limpo, também fechou em 10/10 (em 4 rodadas) e ensinou mais uma coisa: **regra em texto é instável**. A instrução "separe os preços suspeitos e diga a categoria" não fez o Genie citar o Tênis; um **SQL de exemplo** com uma contagem por situação (confirmado × a confirmar), o total e as categorias resolveu na hora. Mexer numa instrução também pode fazer outra pergunta regredir, por isso o teste refaz as 12 perguntas a cada rodada.

---

## Erros comuns

| Sintoma | Causa provável | Como resolver |
|---|---|---|
| Widget "no selected fields to visualize" | Nome do campo no widget diferente do nome no dataset | Peça ao Claude Code para conferir `fields[].name` × `encodings.fieldName` |
| Dashboard vazio em `prod` | Consulta com catálogo fixo (`projetoaovivo.gold.tabela`) | As consultas usam só o nome da tabela; o catálogo vem do `dataset_catalog` do recurso |
| Percentual aparecendo como 700% | `diferenca_pct_*` está em pontos percentuais | Dividir por 100 no dataset antes de usar o formato de % |
| "I don't have access to..." no Genie | Sem `SELECT` na tabela ou sem acesso ao warehouse | Conceda permissão no Unity Catalog |
| Genie responde com a data de hoje | Faltou a instrução do período | Revise as instruções no JSON e faça deploy |
| Genie diz "Tênis 100% mais caro" sem ressalva | Faltou a instrução de preço suspeito | Instrução + SQL de exemplo com `possui_preco_suspeito` |
| Números diferentes da Parte 3 | Pipeline não rodou depois de mudanças | Rode o Job e pergunte de novo |
| Ajuste no Genie sumiu | Foi feito pela interface e o deploy sobrescreveu | Ajuste sempre o JSON do bundle |

---

## Fechando a imersão

| Dia | Você | O diretor |
|---|---|---|
| 1 | Respondeu com SQL e publicou um dashboard | Esperou você |
| 2 | Automatizou a chegada do dado | Recebeu o número atualizado todo dia |
| 3 | Profissionalizou com Git, testes e deploy | Passou a confiar no número |
| 4 | Entregou um dashboard por diretoria e um agente testado | **Pergunta sozinho** |

O que você construiu nesses 4 dias é exatamente o que as empresas estão tentando fazer agora: um dado organizado o suficiente para a IA trabalhar em cima dele.
