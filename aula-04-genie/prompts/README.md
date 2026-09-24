# Aula 4 em 2 prompts

Com estes dois prompts, o Claude Code transforma a gold da Aula 3 em produto para os diretores: um dashboard para cada diretoria e um agente do Genie que responde em português. Tudo como código, dentro do mesmo projeto da Aula 3.

| # | Prompt | O que sai |
|---|---|---|
| 1 | [Um dashboard para cada diretor](./prompt_01.md) | Dashboards "Diretoria Comercial", "Diretoria de Customer Success" e "Diretoria de Pricing" (`src/dashboards/*.lvdash.json` + `resources/*.dashboard.yml`) |
| 2 | [O agente do Genie](./prompt_02.md) | Genie space "Diretoria E-commerce" (`src/genie/` + `resources/diretoria.genie_space.yml`), testado com 10 perguntas e 2 de limite, e o botão **Ask Genie** nos 3 dashboards |

Os prompts rodam na ordem: o prompt 2 liga o Genie aos dashboards criados no prompt 1.

## Antes dos prompts

Você precisa de:
- o projeto da Aula 3 (`ecommerce-pipeline`), com os 4 prompts da Aula 3 executados e o Job verde;
- as 5 golds no catálogo `projetoaovivo`: `vendas_temporais`, `vendas_produtos`, `vendas_detalhadas`, `clientes_segmentacao` e `precos_competitividade`;
- a Databricks CLI autenticada com o perfil `imersao` e o Claude Code com o plugin Databricks (setup no [README da Aula 3](../../aula-03-claude-code/README.md#parte-3-setup-faça-antes-da-aula-se-puder)).

Os prompts leem o perfil e o catálogo do `CLAUDE.md` do projeto, que os prompts da Aula 3 gravaram.

## Como usar

Copie a pasta `prompts/` desta aula para dentro do projeto da Aula 3 (ela pode conviver com a da Aula 3: renomeie para `prompts_aula4/`, por exemplo) e, no Claude Code:

```text
Execute o que está em @prompts_aula4/prompt_01.md
```

Revise antes de passar para o próximo: abra os 3 dashboards, confira os KPIs com os números da tabela abaixo e pergunte o porquê do que não entendeu. Depois:

```text
Execute o que está em @prompts_aula4/prompt_02.md
```

## Como saber se deu certo

| Conferência | Esperado |
|---|---|
| Dashboard Comercial | Receita R$ 974.077,28, 3.020 vendas, ticket R$ 322,54; e-commerce com 2.155 vendas e R$ 705.486,21 |
| Dashboard Customer Success | 50 clientes, 10 VIP com 27,0% da receita, Norte na frente (R$ 333.078,69) |
| Dashboard Pricing | 215 produtos, 35 mais caros que todos (R$ 161.375,09 de receita), 15 com preço suspeito, Tênis +100% |
| Genie | 10 de 10 perguntas certas, e as duas de limite (lucro, "ontem") recusadas sem inventar |
| Dashboards | Botão **Ask Genie** abrindo o space "Diretoria E-commerce" |

Se o Genie errar uma pergunta, não aceite "a IA errou": peça ao Claude Code para mostrar o SQL que o Genie gerou e melhorar o contexto do space (comentário, instrução, join ou SQL de exemplo) até acertar. É o mesmo trabalho que você faria numa empresa.
