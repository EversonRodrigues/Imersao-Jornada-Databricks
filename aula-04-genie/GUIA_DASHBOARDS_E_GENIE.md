# Guia: Dashboards AI/BI e Genie no Databricks

Material de consulta da Aula 4. O [README](./README.md) mostra o passo a passo da aula; este guia explica **como as duas ferramentas funcionam por dentro**, para você saber o que o Claude Code está escrevendo quando roda os prompts e conseguir ajustar sozinho depois.

Os dois leem as mesmas tabelas gold, rodam no mesmo SQL warehouse e respeitam as mesmas permissões do Unity Catalog. A diferença está em quem faz a pergunta:

| | Dashboard AI/BI | Genie |
|---|---|---|
| Quem define a pergunta | Quem montou o dashboard | Quem está usando, em português |
| O que entrega | Os mesmos KPIs e gráficos, todo dia | Uma resposta nova para cada pergunta, com o SQL visível |
| Onde mora a lógica | Nas consultas dos datasets | No contexto do space: tabelas, comentários, instruções e exemplos |
| Como se testa | Conferindo cada KPI contra SQL direto na gold | Com perguntas de resposta conhecida (benchmarks) |
| Como vira código | `*.lvdash.json` + recurso `dashboards` no bundle | `*.geniespace.json` + recurso `genie_spaces` no bundle |

---

## Parte 1: Dashboards AI/BI

O Dashboard AI/BI (antes chamado Lakeview) é a ferramenta de BI nativa do Databricks. Não precisa de licença à parte nem de exportar dado para outra ferramenta: o dashboard consulta a tabela onde ela está.

### Como um dashboard é montado

```
dashboard
├── datasets        ← consultas SQL (ou uma tabela/metric view do Unity Catalog)
├── pages           ← páginas (abas) do dashboard
│   └── widgets     ← KPIs, gráficos, tabelas e textos, cada um ligado a um dataset
├── filtros         ← por campo ou por parâmetro, valendo para os datasets que têm o campo
└── uiSettings      ← tema (cores, fonte) e o botão Ask Genie
```

| Peça | O que é | Na Aula 4 |
|---|---|---|
| **Dataset** | Uma consulta SQL com o dado que os widgets vão usar | `ds_vendas` lê `vendas_detalhadas`, com o canal já traduzido para "E-commerce" e "Loja física" |
| **Widget** | Uma visualização: counter (KPI), barra, linha, pizza, tabela, pivot, mapa, texto | KPI de receita, receita por dia com uma linha por canal, top 10 produtos |
| **Filtro de campo** | Filtra todos os widgets cujo dataset tem aquele campo | Período e canal no dashboard Comercial |
| **Parâmetro** | Um valor que entra na consulta (`:canal`), para filtrar antes de agregar | O top 10 de produtos, que precisa filtrar antes do `LIMIT 10` |
| **Medida** | Uma conta declarada no dataset e reaproveitada pelos widgets (`MEASURE(...)`) | Ticket médio = receita ÷ vendas, igual em todos os widgets |

**Uma regra que evita metade dos erros:** um filtro só afeta os datasets que têm o campo filtrado. Por isso o prompt 1 pede `vendas_detalhadas` (uma linha por venda) como dataset principal: data, canal, categoria, cliente e região estão todos lá, e qualquer filtro alcança todos os gráficos. Um dataset pré-agregado sem a coluna `data` simplesmente ignora o filtro de período.

**Cross-filtering:** clicar numa barra filtra os outros widgets **do mesmo dataset**. Quanto menos datasets, mais o dashboard "conversa" sozinho.

### Rascunho × publicado

| | Rascunho (draft) | Publicado |
|---|---|---|
| Quem vê | Quem edita | Quem recebe o link |
| Muda quando | A cada edição | Só quando alguém publica de novo |
| Credenciais | As de quem está editando | As de quem publicou (credenciais embutidas) ou as de quem está vendo |

Com **credenciais embutidas**, o diretor vê o dashboard sem precisar de acesso às tabelas: as consultas rodam com a permissão de quem publicou. Sem elas, cada pessoa vê só o que o Unity Catalog permite. Pelo bundle, o `databricks bundle deploy` publica o dashboard automaticamente.

### Dashboard como código

Pela interface, o dashboard é arrastar e soltar. Por baixo, ele é um JSON (`.lvdash.json`), e é esse JSON que o Claude Code escreve no prompt 1:

```yaml
# resources/diretoria_comercial.dashboard.yml
resources:
  dashboards:
    diretoria_comercial:
      display_name: Diretoria Comercial
      file_path: ../aula-04-genie/dashboards/diretoria_comercial.lvdash.json
      warehouse_id: ${var.warehouse_id}
      dataset_catalog: ${var.catalogo}   # o catálogo entra aqui...
      dataset_schema: gold
```

```sql
-- ...e não na consulta: FROM vendas_detalhadas, nunca FROM ecommerce.gold.vendas_detalhadas
SELECT data, canal_venda, receita FROM vendas_detalhadas
```

Assim o mesmo JSON serve para `dev` e `prod`, cada um com o seu catálogo. Se alguém editar o dashboard pela interface, o próximo deploy sobrescreve a edição: a mudança precisa voltar para o JSON. Para trazer uma edição feita na interface, use `databricks bundle generate dashboard --existing-id <id>`.

### Boas práticas (as que os prompts seguem)

- **Um dashboard por público.** O diretor de Pricing não precisa rolar por gráficos de clientes para achar os dele.
- **KPIs no topo, depois tendência, depois a tabela para agir.** A tabela de detalhe responde "e agora, onde eu mexo?".
- **Teste cada consulta antes de montar o gráfico**, e confira os KPIs contra SQL direto na gold. Gráfico bonito com número errado é pior que nenhum gráfico.
- **A regra de negócio fica no dataset**, e não espalhada nos widgets: ticket médio, rótulos de canal, "preço a confirmar".
- **Formate pelo significado:** R$ com 2 casas, percentual como percentual. A gold guarda `diferenca_pct_vs_media` em pontos percentuais (10 = 10%); para o formato de % do dashboard, divida por 100.
- **Gráfico com no máximo ~8 cores.** Mais que isso vira tabela ou top N.

### Compartilhar e acompanhar

- **Share** → **Can view**, pelo link publicado.
- **Agendamento e assinatura:** o dashboard publicado pode atualizar num horário fixo e mandar um resumo por e-mail para os assinantes, como os diretores.
- **Ask Genie:** com `uiSettings.genieSpace` apontando para um Genie space, o dashboard ganha um botão que abre a conversa. Assim o diretor sai do gráfico e vai para a pergunta que o gráfico não respondeu.

---

## Parte 2: Genie

O Genie é o agente de dados do Databricks: recebe uma pergunta em linguagem natural, escreve o SQL, roda no warehouse e explica o resultado. Cada **Genie space** (também chamado de agente do Genie) é um agente dedicado a um conjunto de tabelas e a um público. Neste projeto, o space "Diretoria E-commerce" atende os três diretores.

### O que o Genie usa para acertar

O Genie não conhece a sua empresa. Tudo o que ele sabe vem do space, nesta ordem de importância:

| Camada | O que é | Exemplo neste projeto |
|---|---|---|
| **Tabelas** | Poucas, cada uma com um propósito claro | As 5 golds. Nenhuma tabela da bronze ou da silver |
| **Comentários (Unity Catalog)** | Descrição de cada tabela e coluna, lida automaticamente | `clientes_unicos`: "Não somar entre linhas" |
| **Instruções gerais** | Regra de negócio que não cabe numa coluna | "Não existe lucro nos dados"; "hoje e ontem não se respondem" |
| **Joins** | Como as tabelas se ligam, e com que cardinalidade | `vendas_produtos.id_produto = precos_competitividade.id_produto` (1:1) |
| **SQL de exemplo** | Pares pergunta → SQL certo, que o Genie usa como modelo | Hora do dia que mais vende, pela receita média por dia |
| **SQL snippets** | Medidas, filtros e expressões com nome | A medida "ticket médio" |
| **Sinônimos e entity matching** | Palavras do negócio e valores reais das colunas | "faturamento" → `receita`; "Tênis" reconhecido como categoria |
| **Perguntas de exemplo** | O que aparece na tela inicial | Duas por diretoria |

**Comentário bom resolve mais que instrução longa.** A instrução entra para o que não cabe numa coluna: período dos dados, o que fazer com "ontem", como tratar preço suspeito. Instrução demais atrapalha: o Genie passa a seguir regras que conflitam.

### Como uma pergunta vira resposta

```
"Quanto vendemos ontem?"
   │
   ├─ 1. Lê o contexto do space (tabelas, comentários, instruções, exemplos)
   ├─ 2. Escreve o SQL (ou percebe que não deve escrever)
   ├─ 3. Roda no warehouse com as permissões de QUEM PERGUNTOU
   └─ 4. Devolve tabela, gráfico e um resumo em português
   │
   ▼
"Os dados vão de 13/12/2025 a 11/01/2026, então não há vendas de ontem.
 Quer ver o último dia disponível?"
```

- **Show code:** todo resultado mostra o SQL gerado. É assim que você confia na resposta, ou desconfia dela.
- **Permissões:** quem não tem `SELECT` numa tabela também não a vê pelo Genie. Para os diretores usarem o space, eles precisam de **Can run** no space, `SELECT` nas golds e acesso ao warehouse.
- **Esclarecimento:** se a pergunta é ambígua, o Genie pode perguntar de volta, em vez de chutar.

### Genie como código

O space inteiro vira um JSON (o *serialized space*), que o Claude Code escreve no prompt 2:

```yaml
# resources/diretoria.genie_space.yml
resources:
  genie_spaces:
    diretoria_ecommerce:
      title: Diretoria E-commerce
      warehouse_id: ${var.warehouse_id}
      parent_path: /Workspace/Users/${workspace.current_user.userName}
      file_path: ../aula-04-genie/genie/diretoria_ecommerce.geniespace.json
```

Dentro do JSON:

```
data_sources.tables          ← as 5 golds, com sinônimos e entity matching por coluna
instructions.text_instructions   ← as regras gerais
instructions.join_specs          ← os joins
instructions.example_question_sqls   ← pergunta → SQL certo
instructions.sql_snippets        ← medidas como "ticket médio"
config.sample_questions          ← as perguntas da tela inicial
```

Dois cuidados que o teste dos prompts revelou:
- **O catálogo fica escrito no JSON** (`ecommerce.gold.vendas_temporais`). O conteúdo do arquivo não passa por variáveis do bundle.
- **Título repetido na mesma pasta quebra o deploy** (`Node named ... already exists`). Num projeto novo, prefira `parent_path: ${workspace.root_path}`, a pasta do próprio bundle, que é diferente em `dev` e `prod`.

Como no dashboard, ajuste feito pela interface se perde no próximo deploy: edite o JSON.

### Testar antes de entregar

Um Genie sem teste é um risco maior que um dashboard sem teste: ele **responde errado com confiança**. O ciclo que o prompt 2 segue:

```
perguntas com resposta conhecida  →  pergunta ao space pela API  →  compara com SQL direto na gold
        ▲                                                                   │
        └──────── melhora o contexto (comentário, instrução, join, exemplo) ◄┘ se errou
```

- **Não mude o esperado para passar no teste.** Mude o contexto.
- **Não copie a pergunta do teste para os SQLs de exemplo.** O placar sobe, mas você mediu cola, não entendimento.
- **Quando a instrução em texto não pega, mostre o formato em SQL.** No teste, "separe os preços suspeitos" em texto falhou; um SQL de exemplo com a contagem por situação e o total resolveu.
- **Refaça todas as perguntas a cada mudança.** Ajustar uma regra pode fazer outra resposta regredir.
- **Benchmarks:** o próprio space guarda um conjunto de perguntas com o SQL certo e mede o acerto a cada mudança. É a versão "oficial" do teste que o prompt faz pela API.
- **Monitoramento:** depois de entregar, o histórico de conversas mostra o que os diretores perguntam, e o 👍/👎 deles mostra onde o Genie errou. Pergunta que aparece toda hora vira SQL de exemplo; erro recorrente vira instrução.

### O que o Genie não deve fazer (e como impedir)

| Armadilha | O que acontece | O que resolve |
|---|---|---|
| Inventar métrica | "Lucro de R$ 300 mil" | Instrução: não existe custo nem lucro |
| Usar a data de hoje | `current_date()` num dado que termina em 11/01/2026 | Instrução: "hoje" e "ontem" não se respondem |
| Tratar o fim dos dados como hoje | "Ontem" vira 10/01/2026 | A mesma instrução, explícita (apareceu na rodada 1 do teste) |
| Somar o que não soma | Somar `clientes_unicos` de vários dias | Comentário da coluna |
| Média de médias | `AVG(ticket_medio)` | SQL snippet da medida ticket médio |
| Reagir a dado suspeito | "Tênis está 100% mais caro" | Instrução: separar confirmados de preço a confirmar |

### Outras portas para o mesmo Genie

- **API de conversa:** o que o Claude Code usa para testar (`databricks genie start-conversation`). Serve também para levar o Genie a um app, ao Slack ou ao Teams.
- **MCP gerenciado do Genie** (`/api/2.0/mcp/genie/{id_do_space}`): conecta o space a agentes de IA como o Claude Code, como vimos na Aula 3.
- **Ask Genie no dashboard:** o botão que liga os dois mundos.

---

## Na Free Edition

Tudo deste guia funciona na Free Edition: dashboards, Genie, bundles e a API de conversa rodam no **Serverless Starter Warehouse**. Cada gráfico aberto e cada pergunta ao Genie é uma consulta nesse warehouse, então ele liga sozinho quando alguém usa e desliga quando para. Nas primeiras consultas do dia, a espera de alguns segundos é o warehouse subindo.

## Resumo em uma frase

**O dashboard responde as perguntas que você previu; o Genie responde as que ninguém previu. Os dois só acertam porque a gold é limpa, testada e documentada.**
