# MultiMind — Análise Técnica (Fase 0)

> Documento de base da PAP. Define **o que** vamos construir, **como** e **porquê**,
> antes de escrever qualquer linha de código. Todas as decisões aqui registadas
> podem ser revistas, mas qualquer alteração deve ficar documentada em
> [`decisoes-tecnicas.md`](decisoes-tecnicas.md).
>
> **Revisão 1 (após as respostas da secção 20):** orçamento zero para APIs
> (fornecedores gratuitos e modelos locais via Ollama, DT-01), **SQLite** em vez de
> PostgreSQL (DT-02), sem sandbox de execução de código (DT-03), interface
> bilingue (DT-04), âmbito ajustado a ~6 h/semana (DT-05).

---

## Índice

1. [Problema e objetivos](#1-problema-e-objetivos)
2. [Requisitos](#2-requisitos)
3. [Arquitetura proposta](#3-arquitetura-proposta)
4. [Stack recomendada (e o que foi rejeitado)](#4-stack-recomendada)
5. [Estrutura de pastas](#5-estrutura-de-pastas)
6. [Modelo da base de dados](#6-modelo-da-base-de-dados)
7. [Fluxo completo de execução](#7-fluxo-completo-de-execução)
8. [Sistema de agentes e abstração de providers](#8-sistema-de-agentes-e-abstração-de-providers)
9. [Estratégia do orquestrador](#9-estratégia-do-orquestrador)
10. [Estratégia de revisão](#10-estratégia-de-revisão)
11. [Estratégia de memória e contexto](#11-estratégia-de-memória-e-contexto)
12. [Workspace, versionamento, decisões e human-in-the-loop](#12-workspace-versionamento-decisões-e-human-in-the-loop)
13. [Experiências e métricas](#13-experiências-e-métricas)
14. [Segurança](#14-segurança)
15. [Riscos técnicos](#15-riscos-técnicos)
16. [Limitações assumidas](#16-limitações-assumidas)
17. [MVP](#17-mvp)
18. [Roadmap por fases](#18-roadmap-por-fases)
19. [Estimativa de complexidade](#19-estimativa-de-complexidade)
20. [Questões em aberto](#20-questões-em-aberto)

---

## 1. Problema e objetivos

### Problema

Os LLMs atuais são usados quase sempre de forma isolada: um utilizador, um modelo,
uma conversa. Para tarefas complexas (ex.: criar uma aplicação), um único modelo:

- tende a não rever criticamente o próprio trabalho;
- mistura planeamento, execução e verificação numa só resposta;
- não deixa rasto estruturado de **porquê** tomou cada decisão.

Enviar a mesma pergunta a dois chatbots e mostrar duas respostas **não resolve**
este problema — apenas duplica-o.

### Objetivo geral

Construir uma **plataforma de orquestração multiagente** em que LLMs de fornecedores
diferentes (inicialmente OpenAI e Anthropic) colaboram de forma estruturada:
planeiam, dividem trabalho, produzem artefactos num workspace partilhado, revêem-se
mutuamente, corrigem, e chegam a um resultado final — com todo o processo
persistido, observável em tempo real e mensurável.

### Objetivos específicos

| # | Objetivo | Como se demonstra |
|---|----------|-------------------|
| O1 | Decompor uma tarefa num grafo de subtarefas com dependências | Task Board mostra o DAG gerado pelo planner |
| O2 | Atribuir subtarefas a agentes segundo uma política configurável | Cada tarefa mostra o agente e a razão da atribuição |
| O3 | Comunicação mediada entre agentes, persistida e tipificada | Agent Room com mensagens em streaming |
| O4 | Revisão cruzada com ciclo de correção limitado | Histórico de revisões e versões de cada ficheiro |
| O5 | Workspace partilhado com versionamento e autoria | File Viewer com histórico e diff por versão |
| O6 | Registo de decisões com propostas, discussão e justificação | Decision Log |
| O7 | Intervenção humana (pausar, cancelar, escolher, aprovar) | Botões reais que alteram o estado da execução |
| O8 | Comparar estratégias de colaboração com métricas reais | Página de Experiências com tabela comparativa |
| O9 | Arquitetura extensível a novos modelos sem alterar o orquestrador | Adicionar um provider = 1 classe + 1 registo |

---

## 2. Requisitos

### 2.1 Requisitos funcionais

**Projetos e utilizadores**
- RF01 — Registo e autenticação de utilizadores.
- RF02 — Criar, listar, editar e arquivar projetos; cada projeto pertence a um utilizador.
- RF03 — Cada projeto tem um workspace isolado.

**Agentes**
- RF04 — Configurar agentes (nome, provider, modelo, capacidades, system prompt, parâmetros).
- RF05 — Ativar/desativar agentes; testar a ligação de um agente ("ping").

**Execução (run)**
- RF06 — Submeter uma tarefa em linguagem natural e iniciar uma execução com uma estratégia.
- RF07 — O planner gera um grafo de tarefas (títulos, descrições, critérios de aceitação, dependências, capacidade necessária).
- RF08 — Validar o grafo (acíclico, limites de tamanho) antes de executar.
- RF09 — Atribuir cada tarefa a um agente segundo a política da estratégia.
- RF10 — Executar tarefas respeitando dependências (uma tarefa só começa quando todas as dependências estão `COMPLETED`).
- RF11 — Agentes produzem/alteram ficheiros através de ferramentas controladas pelo sistema.
- RF12 — Agentes enviam mensagens uns aos outros através do orquestrador.
- RF13 — Revisão estruturada (`APPROVED` / `NEEDS_REVISION`) com problemas, severidade e sugestões.
- RF14 — Ciclo revisão → correção → revisão com limite de iterações.
- RF15 — Gerar um resultado final (síntese + lista de artefactos + problemas pendentes).

**Observabilidade**
- RF16 — Transmitir em tempo real (streaming) o texto produzido pelos agentes.
- RF17 — Persistir todas as mensagens, tipificadas (utilizador, orquestrador, agente, resultado, revisão, decisão, sistema).
- RF18 — Histórico de versões de cada ficheiro com autor, tarefa, data e diff.
- RF19 — Registo de decisões (questão, propostas por agente, discussão, decisão, justificação, quem decidiu).

**Human-in-the-loop**
- RF20 — Pausar, retomar e cancelar uma execução.
- RF21 — Aprovar/editar o plano antes da execução (opcional por estratégia).
- RF22 — Editar uma tarefa pendente; enviar instruções adicionais a meio.
- RF23 — Responder a pedidos de decisão do sistema (ex.: escolher arquitetura A ou B).
- RF24 — Aprovar ou rejeitar manualmente uma revisão.

**Experiências e métricas**
- RF25 — Registar métricas de cada chamada à API (tokens, latência, sucesso, custo estimado).
- RF26 — Agregar métricas por execução.
- RF27 — Criar uma experiência: a mesma tarefa corrida com várias estratégias, N repetições.
- RF28 — Comparar execuções lado a lado; exportar dados (CSV/JSON) para a documentação.

### 2.2 Requisitos não funcionais

| ID | Requisito |
|----|-----------|
| RNF01 | **Segurança**: API keys só em variáveis de ambiente; nunca no Git, na BD ou no frontend. |
| RNF02 | **Autorização**: um utilizador só acede aos seus projetos. |
| RNF03 | **Robustez**: nenhuma execução pode entrar em ciclo infinito (limites em várias camadas). |
| RNF04 | **Extensibilidade**: novo provider/agente/estratégia sem alterar o núcleo do orquestrador. |
| RNF05 | **Rastreabilidade**: cada alteração a um artefacto está ligada a um agente, tarefa e execução. |
| RNF06 | **Isolamento**: agentes só escrevem dentro do workspace do projeto; nenhum código gerado é executado no processo principal. |
| RNF07 | **Testabilidade**: todo o fluxo testável sem gastar dinheiro (provider simulado determinístico). |
| RNF08 | **Compreensibilidade**: arquitetura que o aluno consegue explicar na defesa, módulo a módulo. |
| RNF09 | **Resiliência**: falhas de API tratadas com retries e backoff; uma falha não corrompe o estado. |
| RNF10 | **Usabilidade**: interface de aplicação real, responsiva, com feedback de estado constante. |

---

## 3. Arquitetura proposta

### 3.1 Visão geral (camadas)

```
┌──────────────────────────────────────────────────────────────────────┐
│  FRONTEND  (React + TypeScript)                                      │
│  Dashboard · Project Workspace · Agent Room · Task Board ·           │
│  File Viewer · Decision Log · Experiments                            │
└───────────────┬───────────────────────────────▲──────────────────────┘
                │ REST (comandos e consultas)    │ SSE (eventos em tempo real)
┌───────────────▼───────────────────────────────┴──────────────────────┐
│  API LAYER  (FastAPI routers — finos, só validação e autorização)    │
├──────────────────────────────────────────────────────────────────────┤
│  APPLICATION SERVICES                                                │
│  projects · agents · tasks · messages · reviews · decisions ·        │
│  workspace · metrics · experiments · interventions                   │
├──────────────────────────────────────────────────────────────────────┤
│  ORCHESTRATION ENGINE                                                │
│  RunManager → Orchestrator → Planner / Scheduler / Assigner /        │
│               TaskExecutor / ReviewCoordinator / DecisionCoordinator │
│               ContextBuilder / Guards / EventBus                     │
├──────────────────────────────┬───────────────────────────────────────┤
│  AGENT RUNTIME               │  WORKSPACE STORE                      │
│  Agent (config) + Provider   │  Versões na BD + espelho em disco     │
├──────────────────────────────┤                                       │
│  PROVIDER ABSTRACTION        │                                       │
│  LLMProvider ◄── OpenAI      │                                       │
│              ◄── Anthropic   │                                       │
│              ◄── Fake (testes)                                        │
├──────────────────────────────┴───────────────────────────────────────┤
│  PERSISTÊNCIA  SQLAlchemy 2.0 → PostgreSQL   (migrações: Alembic)    │
└──────────────────────────────────────────────────────────────────────┘
                   │                          │
            API OpenAI                  API Anthropic
```

### 3.2 Padrões arquiteturais usados (vocabulário para a defesa)

| Padrão | Onde | Porquê |
|--------|------|--------|
| **Mediator (hub-and-spoke)** | Orquestrador | Os agentes nunca falam diretamente; toda a comunicação passa pelo orquestrador, que a valida, persiste e decide quem a recebe. Dá controlo, rastreabilidade e prevenção de loops. |
| **Blackboard** | Workspace + mensagens | Os agentes colaboram sobre uma "memória partilhada" (ficheiros, decisões, resultados) em vez de trocarem conversas longas. |
| **Strategy** | Políticas de atribuição, revisão e planeamento | Uma "estratégia de colaboração" é um objeto de configuração; é isto que as experiências variam. |
| **Adapter** | Providers | Cada API externa é adaptada a uma interface comum `LLMProvider`. |
| **Registry** | Providers, ferramentas, estratégias | Adicionar uma implementação = registá-la; o núcleo não conhece nomes concretos. |
| **State Machine** | Estados da execução e das tarefas | Transições explícitas e validadas; impossível passar de `CANCELLED` para `RUNNING` por engano. |
| **Event Sourcing (leve)** | Tabela `run_events` | Registo append-only de tudo o que aconteceu; alimenta o SSE e permite rever uma execução passada. |

### 3.3 Regras de dependência entre módulos

Para evitar "um ficheiro gigante" e dependências circulares:

1. `providers/` não conhece a base de dados nem os agentes — só sabe falar com APIs.
2. `api/` (routers) só chama serviços; nunca tem lógica de negócio.
3. Os serviços de domínio (`tasks`, `reviews`, `workspace`, …) não conhecem o orquestrador.
4. `orchestration/` usa os serviços de domínio e o agent runtime; é a única camada que "coordena".
5. Toda a comunicação para o frontend passa pelo `EventBus`.

---

## 4. Stack recomendada

Avaliei a stack sugerida componente a componente, com o critério: **resolve um
problema real do projeto e consegues explicá-la na defesa?**

### 4.1 Decisões

| Camada | Escolha | Veredicto | Justificação |
|--------|---------|-----------|--------------|
| Linguagem backend | **Python 3.11+** | ✅ Manter | SDKs oficiais da OpenAI e da Anthropic são de primeira classe em Python; `asyncio` permite várias chamadas a LLMs em paralelo sem threads. |
| Framework web | **FastAPI** | ✅ Manter | Assíncrono nativo (essencial: chamadas a LLMs demoram segundos), validação com Pydantic, documentação OpenAPI automática em `/docs` (útil na defesa). |
| Validação | **Pydantic v2** | ✅ (vem com FastAPI) | Os mesmos modelos validam pedidos HTTP **e** as respostas estruturadas dos LLMs (planos, revisões). |
| ORM | **SQLAlchemy 2.0 (async)** | ✅ Manter | Standard em Python; modelos tipados; abstrai a BD (testes podem usar SQLite). |
| Migrações | **Alembic** | ✅ Manter | O esquema vai evoluir ao longo das fases; migrações versionadas são a forma correta. |
| Base de dados | ~~PostgreSQL 16~~ → **SQLite (WAL)** — ver DT-02 | 🔁 Revisto | O orquestrador escreve continuamente (eventos, mensagens, métricas) enquanto a API lê — o SQLite bloqueia a BD inteira em cada escrita e isso causaria erros `database is locked`. PostgreSQL corre com **um comando** via Docker Compose. Os testes automáticos usam SQLite em memória. |
| Tempo real | **SSE** (Server-Sent Events) | 🔁 Escolhido **em vez de WebSockets** | O fluxo em tempo real é **unidirecional** (servidor → browser: tokens, eventos). Os comandos do utilizador (pausar, aprovar…) são pedidos REST normais. SSE é HTTP simples, reconecta automaticamente e retoma a partir do último evento (`Last-Event-ID`). WebSockets trariam gestão de ligação bidirecional sem benefício. |
| Execução em background | **asyncio tasks** no próprio processo, geridas por um `RunManager` | 🔁 **Sem Celery/Redis** | Uma fila distribuída é para vários servidores e milhares de jobs. Aqui há poucas execuções simultâneas. O estado vive na BD, por isso uma execução interrompida pode ser retomada. Limitação documentada: um só processo. |
| Frontend | **React + TypeScript + Vite** | ✅ Manter | Tipos partilhados com o contrato da API reduzem erros; Vite é simples e rápido. |
| Routing | **React Router** | ✅ | Várias páginas reais (dashboard, projeto, agent room…). |
| Dados no frontend | **TanStack Query** | ➕ Justificado | Elimina código repetitivo de loading/erro/cache e permite invalidar dados quando chega um evento SSE (ex.: "tarefa concluída" → recarregar Task Board). |
| Estilos | **Tailwind CSS** | ➕ Justificado | Consistência visual rápida sem escrever CSS de raiz; fácil de explicar. |
| Gráficos | **Recharts** | ➕ Só na fase de métricas | Comparação de experiências. |
| Diff | **`difflib`** (Python, biblioteca padrão) | ✅ | Diffs calculados no backend; o frontend só os mostra. Zero dependências. |
| Workspace | **BD como fonte de verdade + espelho em disco**; exportação **Git** opcional | 🔁 Ajustado | Ver secção 12.1. |
| Autenticação | **Cookie httpOnly com token assinado** + passwords com **argon2/bcrypt** | ✅ | O `EventSource` do browser (SSE) não permite cabeçalhos `Authorization`; um cookie httpOnly funciona e não fica acessível a JavaScript (protege contra XSS). |
| Qualidade | **ruff** (lint+format), **pytest**, **mypy** (opcional), **ESLint + tsc** | ✅ | Ferramentas standard, uma por função. |
| Infra local | ~~Docker Compose~~ → nada a instalar para a BD (SQLite) — ver DT-02 | 🔁 Revisto | Backend e frontend correm diretamente na máquina durante o desenvolvimento (mais fácil de depurar). |

### 4.2 Tecnologias deliberadamente rejeitadas

| Tecnologia | Porque não |
|------------|-----------|
| **LangChain / LangGraph / AutoGen / CrewAI** | Resolvem exatamente o que a PAP tem de demonstrar. Se o orquestrador vier de uma framework, a infraestrutura deixa de ser tua. Usamos só os SDKs oficiais dos fornecedores. **Decisão mais importante desta secção.** |
| Celery + Redis | Complexidade de sistema distribuído sem necessidade (ver acima). |
| Base de dados vetorial / RAG | O workspace de uma execução é pequeno (dezenas de ficheiros). A seleção explícita de contexto é mais previsível e mais fácil de explicar do que pesquisa por embeddings. Pode ser uma extensão futura. |
| Next.js / SSR | Não precisamos de SEO nem renderização no servidor; uma SPA chega. |
| Kubernetes, microserviços | Um monólito modular é a arquitetura certa para esta escala. |
| Django | Excelente, mas síncrono por natureza e com um ORM/admin que não trazem vantagem aqui. |
| Monaco Editor | Pesado; para *visualizar* código basta um highlighter leve. |

---

## 5. Estrutura de pastas

Organização **por domínio**: cada módulo de domínio tem os mesmos quatro ficheiros
(`models.py` tabelas, `schemas.py` contratos Pydantic, `service.py` lógica,
`router.py` endpoints). Assim sabes sempre onde procurar.

```
PAP---2.0/
├── README.md
├── .gitignore                    # inclui .env, workspaces/, node_modules/
├── .env.example                  # nomes das variáveis, sem valores reais
├── docs/                         # documentação da PAP (ver 18.3)
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/                  # migrações
│   ├── app/
│   │   ├── main.py               # cria a app FastAPI, regista routers
│   │   ├── core/                 # config (env), segurança, logging, erros
│   │   ├── db/                   # engine, sessão, Base declarativa
│   │   ├── auth/                 # users, login, dependência current_user
│   │   ├── projects/
│   │   ├── agents/               # config de agentes + AgentRuntime
│   │   ├── providers/
│   │   │   ├── base.py           # LLMProvider (interface) + tipos normalizados
│   │   │   ├── registry.py       # "openai" → OpenAIProvider, ...
│   │   │   ├── openai_provider.py
│   │   │   ├── anthropic_provider.py
│   │   │   ├── fake_provider.py  # determinístico, para testes
│   │   │   └── pricing.py        # preços por modelo (configuráveis)
│   │   ├── orchestration/
│   │   │   ├── run_manager.py    # ciclo de vida das execuções (start/pause/cancel)
│   │   │   ├── orchestrator.py   # máquina de estados de uma execução
│   │   │   ├── planner.py        # tarefa → grafo de tarefas
│   │   │   ├── task_graph.py     # validação do DAG, ordem topológica
│   │   │   ├── scheduler.py      # que tarefas estão prontas
│   │   │   ├── assignment.py     # políticas de atribuição de agentes
│   │   │   ├── executor.py       # executa uma tarefa (loop de ferramentas)
│   │   │   ├── review_coordinator.py
│   │   │   ├── decision_coordinator.py
│   │   │   ├── context_builder.py
│   │   │   ├── guards.py         # limites: iterações, chamadas, tokens, custo, tempo
│   │   │   ├── strategies.py     # definição das estratégias de colaboração
│   │   │   ├── tools.py          # ferramentas disponíveis aos agentes
│   │   │   └── prompts/          # templates de prompts (ficheiros, não strings no código)
│   │   ├── runs/                 # entidade Run (execução)
│   │   ├── tasks/
│   │   ├── messages/
│   │   ├── reviews/
│   │   ├── decisions/
│   │   ├── interventions/        # pedidos ao humano e respostas
│   │   ├── workspace/            # artefactos, versões, diff, segurança de caminhos
│   │   ├── events/               # EventBus + endpoint SSE
│   │   ├── metrics/
│   │   └── experiments/
│   └── tests/
│       ├── unit/
│       ├── integration/          # execuções completas com FakeProvider
│       └── live/                 # testes com APIs reais (desligados por defeito)
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── app/                  # router, layout, providers
│       ├── api/                  # cliente HTTP + cliente SSE + tipos
│       ├── components/           # UI genérica (Button, Badge, Panel, ...)
│       ├── features/
│       │   ├── dashboard/
│       │   ├── projects/
│       │   ├── agent-room/
│       │   ├── task-board/
│       │   ├── files/
│       │   ├── decisions/
│       │   ├── agents/
│       │   └── experiments/
│       ├── hooks/                # useRunEvents, useAuth, ...
│       └── lib/
│
└── workspaces/                   # espelho em disco dos workspaces (fora do Git)
```

**Alteração à estrutura sugerida:** acrescentei `runs/` (execução), `interventions/`
(human-in-the-loop) e `events/` (tempo real) como módulos próprios, e separei o
orquestrador em vários ficheiros pequenos com uma responsabilidade cada.

---

## 6. Modelo da base de dados

### 6.1 Conceito-chave novo: **Run** (execução)

Um projeto pode ter **várias execuções**. Cada vez que carregas em "Run Agents"
com uma tarefa e uma estratégia, nasce um `run`. As tarefas, mensagens, revisões,
decisões e métricas pertencem a um run. Sem isto, não seria possível comparar
estratégias sobre o mesmo projeto nem rever execuções antigas.

### 6.2 Diagrama entidade-relação (simplificado)

```
users 1───* projects 1───* runs *───0..1 experiments
                 │           │
                 │           ├──* tasks ──* task_dependencies (auto-relação N:N)
                 │           │      │
                 │           │      ├──* reviews 1──* review_issues
                 │           │      └──* llm_calls
                 │           ├──* messages
                 │           ├──* decisions 1──* decision_proposals
                 │           ├──* interventions
                 │           ├──* run_events
                 │           └──1 run_metrics
                 │
                 └──* artifacts 1──* artifact_versions ─→ (task, run, agent)

agents (catálogo) ←── referenciado por tasks, messages, reviews, versions, llm_calls
```

### 6.3 Tabelas

Convenções: `id` UUID; datas em UTC; enums guardados como texto com `CHECK`.

**users**
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| email | text UNIQUE | |
| display_name | text | |
| password_hash | text | argon2/bcrypt, nunca a password |
| created_at | timestamptz | |

**projects**
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| owner_id | uuid FK → users | autorização por projeto |
| name, description | text | |
| status | enum `ACTIVE/ARCHIVED` | |
| created_at, updated_at | timestamptz | |

> Partilha de projetos entre utilizadores (`project_members` com papéis) fica
> desenhada mas fora do MVP.

**agents**
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| owner_id | uuid FK → users, nullable | null = agente de sistema |
| name | text | "ChatGPT", "Claude", "Claude-Reviewer"… |
| provider | text | chave no registry: `openai`, `anthropic`, `fake` |
| model | text | configurável, ex.: definido no `.env` |
| capabilities | text[] | `planning`, `architecture`, `coding`, `review`, `testing`, `documentation` |
| system_prompt | text | persona base |
| config | jsonb | `temperature`, `max_output_tokens`… (pequeno, validado por Pydantic) |
| enabled | bool | |
| created_at | timestamptz | |

**runs**
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| project_id | uuid FK → projects | |
| experiment_id | uuid FK → experiments, nullable | |
| objective | text | a tarefa escrita pelo utilizador |
| strategy_key | text | ex.: `cross_review`, `single_openai` |
| strategy_config | jsonb | snapshot da estratégia usada (reprodutibilidade) |
| limits | jsonb | snapshot dos limites (max chamadas, tokens, custo, tempo) |
| status | enum | `PENDING, PLANNING, AWAITING_PLAN_APPROVAL, RUNNING, PAUSED, WAITING_USER, FINALIZING, COMPLETED, FAILED, CANCELLED` |
| final_result | text | síntese final |
| failure_reason | text | |
| created_by | uuid FK → users | |
| started_at, finished_at | timestamptz | |

**tasks**
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| run_id | uuid FK → runs | |
| project_id | uuid FK → projects | redundante mas facilita consultas/autorização |
| key | text | id curto do planner, ex.: `T3` |
| title, description | text | |
| acceptance_criteria | text | usado pelo revisor |
| required_capability | text | usado pela política de atribuição |
| status | enum | `PENDING, RUNNING, WAITING, REVIEW, FAILED, COMPLETED, CANCELLED` |
| assigned_agent_id | uuid FK → agents | |
| assignment_reason | text | "capacidade coding; estratégia cross_review" |
| priority | int | |
| result | text | resumo produzido pelo agente |
| iteration_count | int | nº de execuções/correções |
| max_iterations | int | |
| created_by | enum `PLANNER/USER` | |
| created_at, started_at, completed_at | timestamptz | |

**task_dependencies** — `(task_id FK, depends_on_id FK)` PK composta. Relação N:N
real, não uma lista JSON; permite consultas e integridade referencial.

**messages**
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| run_id | uuid FK | |
| task_id | uuid FK, nullable | |
| kind | enum | `USER, ORCHESTRATOR, AGENT, TASK_RESULT, REVIEW, DECISION, SYSTEM` |
| sender_agent_id | uuid FK, nullable | |
| sender_user_id | uuid FK, nullable | |
| recipient_agent_id | uuid FK, nullable | null = difusão / todos |
| content | text | |
| metadata | jsonb | referências (review_id, decision_id, ficheiros) |
| created_at | timestamptz | |

**artifacts**
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| project_id | uuid FK | |
| path | text | relativo ao workspace, normalizado; UNIQUE(project_id, path) |
| current_version_id | uuid FK → artifact_versions, nullable | |
| created_by_agent_id / created_by_user_id | uuid FK | |
| created_at | timestamptz | |
| deleted_at | timestamptz, nullable | eliminação lógica (nunca se perde histórico) |

**artifact_versions**
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| artifact_id | uuid FK | |
| version_number | int | UNIQUE(artifact_id, version_number) |
| parent_version_id | uuid FK, nullable | versão sobre a qual foi feita a alteração |
| content | text | limite de tamanho (ex.: 200 KB) |
| content_hash | text | SHA-256; deteta "correções" que não mudam nada |
| size_bytes | int | |
| author_agent_id / author_user_id | uuid FK | |
| run_id, task_id | uuid FK | **liga cada alteração à tarefa e à execução** |
| change_kind | enum | `CREATE, MODIFY, REVISION, DELETE` |
| change_summary | text | escrito pelo agente |
| created_at | timestamptz | |

**reviews**
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| task_id | uuid FK | |
| round | int | 1, 2, 3… |
| reviewer_agent_id | uuid FK | |
| author_agent_id | uuid FK | |
| verdict | enum `APPROVED/NEEDS_REVISION` | |
| summary | text | |
| reviewed_versions | jsonb | lista de ids de versões avaliadas |
| human_override | enum `NONE/FORCE_APPROVE/FORCE_REVISION` | |
| human_comment | text | |
| created_at | timestamptz | |

**review_issues** — `id, review_id FK, severity (CRITICAL/MAJOR/MINOR/INFO),
file_path, description, suggestion, resolved (bool), resolved_in_version_id FK`.

**decisions**
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| run_id | uuid FK | |
| number | int | #1, #2… por run |
| question | text | "Que arquitetura usar?" |
| discussion_summary | text | |
| chosen_proposal_id | uuid FK → decision_proposals | |
| justification | text | |
| decided_by | enum `ARBITER_AGENT/CONSENSUS/USER/ORCHESTRATOR` | |
| status | enum `OPEN/AWAITING_USER/DECIDED` | |
| created_at, decided_at | timestamptz | |

**decision_proposals** — `id, decision_id FK, agent_id FK, label (A/B), content, rationale`.

**interventions** (pedidos ao humano)
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| run_id | uuid FK | |
| kind | enum | `APPROVE_PLAN, CHOOSE_OPTION, REVIEW_ESCALATION, BUDGET_EXCEEDED` |
| prompt | text | |
| options | jsonb | |
| status | enum `PENDING/ANSWERED/EXPIRED` | |
| response | jsonb | |
| responded_by | uuid FK → users | |
| created_at, answered_at | timestamptz | |

**llm_calls** (métricas em bruto, uma linha por chamada à API)
| coluna | tipo | notas |
|--------|------|-------|
| id | uuid PK | |
| run_id, task_id, agent_id | uuid FK | |
| provider, model | text | modelo efetivamente devolvido pela API |
| purpose | enum | `PLAN, EXECUTE, REVIEW, REVISE, DECIDE, FINALIZE, PING` |
| input_tokens, output_tokens | int, nullable | nulos se a API não fornecer |
| latency_ms | int | |
| success | bool | |
| error_type | text | `rate_limit`, `timeout`, `invalid_output`… |
| estimated_cost_usd | numeric | tokens × preço configurado |
| started_at | timestamptz | |

**run_metrics** (agregado, calculado no fim do run — 1:1 com runs)
`run_id PK/FK, execution_time_s, api_calls, failed_calls, input_tokens,
output_tokens, tasks_total, tasks_completed, tasks_failed, reviews, revisions,
decisions, human_interventions, estimated_cost_usd, final_status`.

**experiments** — `id, owner_id FK, name, description, objective,
strategies (text[]), repetitions, created_at`. Os runs apontam para a experiência.

**run_events** (registo append-only para tempo real e replay)
`id bigserial PK (ordem global), run_id FK, type, payload jsonb (pequeno), created_at`.
Os *tokens* de streaming **não** são guardados aqui (seriam milhares de linhas);
guarda-se a mensagem final completa em `messages`.

### 6.4 Porque não "um JSON gigante"

Cada conceito tem tabela própria com chaves estrangeiras. Os campos `jsonb` só
existem para dados **pequenos e sem necessidade de consulta relacional** (config
de um agente, snapshot de limites). Isto permite, por exemplo, uma consulta SQL
simples como "todas as versões criadas pelo Claude em tarefas de revisão".

---

## 7. Fluxo completo de execução

### 7.1 Visão macro

```
USER ──"Cria uma app de inventário"──► POST /projects/{id}/runs
                                            │
                                     RunManager.start()
                                            │  (asyncio task em background)
                                            ▼
┌──────────────────────── ORCHESTRATOR (máquina de estados) ─────────────────────────┐
│                                                                                     │
│  PLANNING ──► Planner chama agente planner → plano estruturado (JSON validado)     │
│     │         valida DAG (sem ciclos, ≤ N tarefas) → cria tasks + dependências     │
│     │         decisões-chave detetadas? → DecisionCoordinator (debate)             │
│     ▼                                                                               │
│  [AWAITING_PLAN_APPROVAL]  (opcional) ◄── utilizador aprova/edita plano             │
│     ▼                                                                               │
│  RUNNING ── loop:                                                                   │
│     │   Guards.check()  (iterações, chamadas, tokens, custo, tempo, pausa, cancel)  │
│     │   Scheduler.ready_tasks()  → tarefas PENDING com dependências COMPLETED       │
│     │   Assigner.assign(task)    → escolhe agente segundo a estratégia              │
│     │   Executor.run(task)       → ContextBuilder + chamada LLM + ferramentas       │
│     │        └─ agente escreve ficheiros (versões), envia mensagens, entrega result │
│     │   ReviewCoordinator        → revisor ≠ autor → APPROVED / NEEDS_REVISION      │
│     │        └─ NEEDS_REVISION → autor corrige → nova revisão (≤ max rondas)        │
│     │   task → COMPLETED                                                            │
│     │   até: todas COMPLETED | falha irrecuperável | limite | cancelamento          │
│     ▼                                                                               │
│  FINALIZING ──► agente sintetizador produz relatório final                          │
│     ▼                                                                               │
│  COMPLETED ──► calcula run_metrics                                                  │
└─────────────────────────────────────────────────────────────────────────────────────┘
         │ cada passo publica eventos no EventBus → run_events + SSE → frontend
```

### 7.2 Diagrama de sequência — uma tarefa com revisão

```
Orchestrator     Executor      Claude(autor)   Workspace    ReviewCoord   ChatGPT(revisor)   UI(SSE)
    │ run(T3)       │               │              │             │               │             │
    │──────────────►│ contexto      │              │             │               │             │
    │               │──────────────►│ (stream)     │             │               │   tokens ──►│
    │               │◄── write_file("src/api.py") ─│             │               │             │
    │               │──────────────────────────────►│ v1         │               │  evento ───►│
    │               │◄── submit_result(resumo) ─────│             │               │             │
    │◄── resultado ─│               │              │             │               │             │
    │ review(T3) ──────────────────────────────────────────────►│ contexto      │             │
    │               │               │              │             │──────────────►│ (stream) ──►│
    │               │               │              │             │◄─submit_review(NEEDS_REVISION, issues)
    │◄───────────────────────────────── revisão ronda 1 ─────────│               │  evento ───►│
    │ run(T3, feedback)─────────────►│ corrige      │             │               │             │
    │               │               │──────────────►│ v2 (REVISION)             │  evento ───►│
    │ review(T3) ronda 2 ────────────────────────────────────────►──────────────►│             │
    │◄───────────────────────────────── APPROVED ────────────────│               │  evento ───►│
    │ T3 → COMPLETED; desbloqueia T4, T5                                                       │
```

### 7.3 Exemplo concreto

Tarefa: *"Cria uma pequena aplicação web para gerir o inventário de uma loja."*
Estratégia: `plan_implement_review` (ChatGPT planeia → Claude implementa → ChatGPT revê).

1. **Planner (ChatGPT)** devolve 6 tarefas: T1 arquitetura, T2 modelo de dados (dep. T1),
   T3 backend (dep. T2), T4 frontend (dep. T3), T5 testes (dep. T3), T6 revisão final (dep. T4, T5).
   Identifica uma decisão em aberto: "REST vs. renderização no servidor".
2. **DecisionCoordinator** pede proposta a ambos os agentes (em paralelo), cada um critica
   a do outro, o árbitro (ou o utilizador) decide → **Decision #1** registada.
3. **Scheduler**: só T1 está pronta. Atribuída a ChatGPT (capacidade `architecture`).
4. T1 produz `docs/ARCHITECTURE.md` (v1). Revisão por Claude → `APPROVED`.
5. T2 → Claude → `src/models.py` v1 → revisão ChatGPT → `NEEDS_REVISION` (falta
   validação de stock negativo, severidade MAJOR) → Claude cria v2 → `APPROVED`.
6. T4 e T5 ficam prontas ao mesmo tempo e podem correr **em paralelo**.
7. Finalização: relatório com ficheiros produzidos, decisões, problemas não resolvidos.

---

## 8. Sistema de agentes e abstração de providers

### 8.1 Separação de responsabilidades

```
Agent (dados, BD)          AgentRuntime (execução)              LLMProvider (transporte)
─────────────────          ───────────────────────              ────────────────────────
id, name                   agent + provider                      generate()
provider: "anthropic" ───► registry.get("anthropic") ──────────► stream()
model, capabilities        aplica system_prompt e config         count_tokens()
system_prompt, config      regista llm_calls (métricas)          get_model_info()
```

- **Agent** = *quem* (persona, papel, modelo, capacidades). Vive na BD, editável na UI.
- **LLMProvider** = *como* se fala com uma API. Não sabe nada de tarefas nem de BD.
- **AgentRuntime** = junta os dois, e é o único ponto onde se medem chamadas.

Consequência: podes ter **vários agentes no mesmo provider** (ex.: "Claude-Coder" e
"Claude-Reviewer" com prompts diferentes) — útil para experiências.

### 8.2 Interface do provider (desenho, não implementação final)

```python
class LLMProvider(ABC):
    name: ClassVar[str]                       # "openai", "anthropic", "fake"

    async def generate(self, request: GenerationRequest) -> GenerationResult: ...
    def stream(self, request: GenerationRequest) -> AsyncIterator[StreamEvent]: ...
    async def count_tokens(self, request: GenerationRequest) -> int | None: ...
    def get_model_info(self, model: str) -> ModelInfo: ...    # contexto máx., preço

# Tipos normalizados — iguais para todos os providers
GenerationRequest: model, system, messages[ChatMessage], tools[ToolSpec],
                   tool_choice, temperature, max_output_tokens
GenerationResult:  text, tool_calls[ToolCall], usage(input, output), stop_reason, model
StreamEvent:       TextDelta | ToolCallStart | ToolCallDelta | ToolCallEnd | Usage | Done
```

As diferenças entre APIs (formato das mensagens, como se declaram ferramentas, onde
vêm os tokens no streaming, nomes dos erros) ficam **dentro** de
`openai_provider.py` e `anthropic_provider.py`. O resto da aplicação nunca tem
`if provider == "openai"`. O único sítio onde o nome aparece é o registry:

```python
PROVIDERS = {"openai": OpenAIProvider, "anthropic": AnthropicProvider, "fake": FakeProvider}
```

Adicionar Gemini, um modelo local (ex.: via servidor compatível com a API OpenAI) ou
qualquer outro = escrever uma classe e registá-la. O orquestrador não muda.

### 8.3 Como os agentes "agem": ferramentas (tool calling)

Ambas as APIs suportam *tool calling* nativamente. Em vez de pedir ao modelo para
"escrever código dentro do texto" e depois tentar extraí-lo, damos-lhe ferramentas
com esquema estrito, que **o sistema** executa:

| Ferramenta | Efeito | Disponível em |
|------------|--------|---------------|
| `list_files()` | árvore do workspace | execução, revisão |
| `read_file(path)` | conteúdo da versão atual (limitado) | execução, revisão |
| `write_file(path, content, summary)` | cria **nova versão** (nunca sobrescreve) | execução |
| `send_message(to, content)` | mensagem a outro agente via orquestrador | execução, revisão |
| `raise_decision(question, options)` | abre uma decisão no Decision Log | execução |
| `submit_plan(tasks, open_questions)` | entrega o plano (termina a chamada) | planeamento |
| `submit_result(summary)` | entrega o resultado da tarefa | execução |
| `submit_review(verdict, issues, summary)` | entrega a revisão | revisão |
| `submit_proposal(label, content, rationale)` | proposta numa decisão | decisão |

Vantagens: respostas estruturadas validadas por Pydantic; nenhum acesso direto ao
disco; cada ação fica registada; nada é executado como código. As ferramentas
`submit_*` são forçadas (`tool_choice`) para garantir output estruturado.

Se o JSON devolvido for inválido: 1 nova tentativa com a mensagem de erro de
validação; se falhar outra vez, a chamada conta como `failed_call` e a tarefa
segue as regras de falha.

### 8.4 Capacidades

Lista fechada (enum): `planning, architecture, coding, review, testing,
documentation, synthesis`. O planner indica a capacidade necessária de cada
tarefa; a política de atribuição usa-a. Novos tipos de agente (ex.: "especialista
em testes") = novo agente com capacidade `testing` e prompt próprio.

---

## 9. Estratégia do orquestrador

### 9.1 Componentes (um ficheiro, uma responsabilidade)

| Componente | Responsabilidade |
|------------|------------------|
| `RunManager` | Mantém o registo de execuções ativas (asyncio tasks); start / pause / resume / cancel; ao arrancar o servidor, marca runs órfãos como `PAUSED` para poderem ser retomados. |
| `Orchestrator` | Máquina de estados de um run. Chama os restantes componentes. Não fala diretamente com APIs. |
| `Planner` | Constrói o prompt de planeamento, chama o agente planner, valida o plano. |
| `TaskGraph` | Validação do DAG (deteção de ciclos com ordenação topológica de Kahn), limites (nº de tarefas, profundidade). |
| `Scheduler` | Devolve tarefas prontas (todas as dependências `COMPLETED`), ordenadas por prioridade; respeita `max_parallel_tasks`. |
| `Assigner` | Aplica a política de atribuição da estratégia. |
| `TaskExecutor` | Loop de ferramentas de uma tarefa: chama o agente, executa ferramentas pedidas, devolve resultados ao agente, até `submit_result` ou limite de passos. |
| `ReviewCoordinator` | Ciclo revisão/correção (secção 10). |
| `DecisionCoordinator` | Debate estruturado entre agentes e escalada para o utilizador. |
| `ContextBuilder` | Monta o contexto de cada chamada (secção 11). |
| `Guards` | Verifica todos os limites antes de cada passo. |
| `EventBus` | Publica eventos (BD + subscritores SSE). |

### 9.2 Estratégias de colaboração (o que as experiências comparam)

Uma estratégia é **configuração**, não código:

```yaml
key: plan_implement_review
planner: chatgpt
assignment: { policy: role_map, roles: { coding: claude, testing: claude, "*": chatgpt } }
review:     { enabled: true, reviewer: other_agent, max_rounds: 2 }
decisions:  { debate: true, arbiter: user }        # ou: chatgpt / claude / planner
human:      { approve_plan: false }
limits:     { max_llm_calls: 60, max_tokens: 400000, max_cost_usd: 2.0, max_minutes: 20 }
```

Estratégias pré-definidas iniciais:

| Chave | Descrição |
|-------|-----------|
| `single_openai` | ChatGPT faz tudo (planeia, executa, revê-se a si próprio ou sem revisão) |
| `single_anthropic` | Claude faz tudo |
| `collaborative` | Atribuição por capacidades entre os dois; revisão cruzada |
| `plan_implement_review` | ChatGPT planeia → Claude implementa → ChatGPT revê |
| `plan_implement_review_inv` | O inverso (importante para não enviesar a experiência) |

Políticas de atribuição (`assignment.py`): `single_agent`, `role_map`,
`capability_match` (agente com a capacidade; desempate por menor carga),
`round_robin`. Novas políticas = nova classe registada.

### 9.3 Estados e transições das tarefas

```
             deps COMPLETED
  PENDING ─────────────────► RUNNING ──submit_result──► REVIEW ──APPROVED──► COMPLETED
     ▲                          ▲                          │
     │ utilizador edita         └──── NEEDS_REVISION ──────┘ (iteration_count++)
     │                                                     │ max rondas atingido
  WAITING ◄──── pedido ao humano (escalada/decisão) ◄──────┘
     │
     └─► FAILED (erros repetidos / limite)      qualquer estado ─► CANCELLED
```

Nota: "bloqueada por dependências" **não** é um estado próprio — é `PENDING` e o
Scheduler calcula se está pronta. `WAITING` significa "à espera do utilizador".
Se uma dependência falha, as tarefas dependentes passam a `CANCELLED` com motivo.

### 9.4 Prevenção de loops — limites em camadas

| Nível | Limite | Ao atingir |
|-------|--------|-----------|
| Chamada | timeout (ex.: 120 s), 3 retries com backoff exponencial em erros transitórios (429, 5xx) | `failed_call` |
| Execução de tarefa | máx. passos de ferramentas (ex.: 15), máx. tamanho por ficheiro | força `submit_result` / falha |
| Revisão | `max_review_rounds` (ex.: 2–3) | escalada ao utilizador ou aceitação com problemas registados (configurável) |
| Sem progresso | nova versão com o mesmo `content_hash`, ou mesmos problemas repetidos | termina o ciclo de revisão |
| Plano | máx. tarefas (ex.: 12), DAG acíclico | plano rejeitado → 1 nova tentativa |
| Mensagens | máx. mensagens agente↔agente por tarefa | orquestrador deixa de encaminhar |
| Run | máx. chamadas, tokens, custo estimado, tempo total | `WAITING_USER` (pedir mais orçamento) ou `FAILED` |

Os agentes nunca decidem sozinhos "continuar para sempre": **só o orquestrador
decide o próximo passo**, e decide sempre depois de consultar os `Guards`.

---

## 10. Estratégia de revisão

### 10.1 Seleção do revisor
Definida pela estratégia: `other_agent` (qualquer agente diferente do autor, com
capacidade `review`), um agente fixo, `self` (para a experiência "sozinho") ou
`none`. Por defeito o revisor **nunca é o autor**.

### 10.2 O que o revisor recebe
- a tarefa original e os **critérios de aceitação**;
- as versões produzidas nesta tarefa, **com diff** face à versão anterior;
- contexto do projeto (objetivo, decisões tomadas, árvore de ficheiros);
- nas rondas ≥ 2: a revisão anterior e a lista de problemas marcados como corrigidos;
- uma **rubrica** fixa: correção, completude face aos critérios, coerência com as
  decisões, qualidade/legibilidade, segurança.

### 10.3 O que o revisor devolve (via `submit_review`, esquema estrito)

```json
{
  "verdict": "NEEDS_REVISION",
  "summary": "O endpoint de atualização não valida stock negativo.",
  "issues": [
    { "severity": "MAJOR", "file": "src/api.py",
      "description": "PUT /items/{id} aceita quantity < 0",
      "suggestion": "Validar com Field(ge=0) no schema." }
  ]
}
```

Regra de consistência aplicada pelo orquestrador (não confiamos cegamente no modelo):
se existir um problema `CRITICAL` ou `MAJOR`, o veredicto é tratado como
`NEEDS_REVISION`, mesmo que o revisor diga `APPROVED`. Isto fica registado.

### 10.4 Ciclo
```
EXECUTE → REVIEW ─APPROVED─────────────────────────────► COMPLETED
             └─NEEDS_REVISION → REVISION (autor recebe issues) → REVIEW (ronda+1)
                                  └ ronda > max → ESCALATE (utilizador) ou COMPLETED_COM_PROBLEMAS
```

### 10.5 Intervenção humana na revisão
O utilizador pode, em qualquer revisão: **forçar aprovação**, **forçar nova revisão**
com um comentário próprio (que entra no contexto do autor). Fica em
`reviews.human_override`.

### 10.6 Risco conhecido: revisões complacentes
LLMs tendem a aprovar facilmente. Mitigações: rubrica explícita, pedir sempre pelo
menos uma observação (mesmo `INFO`), revisor de outro fornecedor, e medir nas
experiências a taxa de `NEEDS_REVISION` por estratégia.

---

## 11. Estratégia de memória e contexto

Os LLMs **não têm memória** entre chamadas. Toda a "memória" do MultiMind é
reconstruída pelo `ContextBuilder` a partir da BD, em cada chamada. Isto é uma
vantagem: sabemos exatamente o que cada agente viu (e podemos mostrá-lo na UI).

### 11.1 Camadas de memória

| Camada | Conteúdo | Guardada em |
|--------|----------|-------------|
| Identidade | system prompt do agente + papel nesta chamada | `agents`, `prompts/` |
| Projeto | objetivo do run, resumo do plano, decisões tomadas | `runs`, `tasks`, `decisions` |
| Tarefa | descrição, critérios, resultado das dependências (**resumos**) | `tasks.result` |
| Artefactos | árvore de ficheiros (sempre) + conteúdo dos ficheiros relevantes | `artifact_versions` |
| Conversa | mensagens dirigidas ao agente ou sobre a tarefa (últimas N) | `messages` |
| Feedback | revisão anterior e problemas por resolver | `reviews`, `review_issues` |
| Instruções humanas | instruções adicionais do utilizador | `messages` (kind `USER`) |

### 11.2 Orçamento de contexto
Cada chamada tem um orçamento de tokens (ex.: 60% da janela do modelo). O builder
enche por **prioridade**: identidade → tarefa → feedback → instruções humanas →
decisões → resumos de dependências → ficheiros relevantes → mensagens recentes. O
que não cabe é omitido (com nota "N ficheiros omitidos, usa `read_file`").

### 11.3 Resumos em vez de transcrições
No fim de cada tarefa o agente entrega um `summary` curto (`submit_result`). As
tarefas seguintes recebem os resumos, não as conversas inteiras — é isto que evita
que o contexto cresça sem limite.

### 11.4 Contexto sob pedido
Se precisar de mais, o agente usa `read_file` / `list_files` (limitados em número
de chamadas e tamanho). "Ficheiros relevantes" por defeito = ficheiros criados
pelas dependências + ficheiros mencionados na descrição da tarefa.

---

## 12. Workspace, versionamento, decisões e human-in-the-loop

### 12.1 Workspace e versões — decisão sobre Git

| Opção | Prós | Contras |
|-------|------|---------|
| Só Git | histórico e diffs "de graça" | ligar commits a tarefas/agentes exige convenções frágeis; consultas lentas; duas fontes de verdade |
| **BD como fonte de verdade + espelho em disco** ✅ | cada versão é uma linha com agente, tarefa, run; consultas SQL diretas; diff com `difflib` | temos de implementar o versionamento (é simples e é trabalho *teu*, bom para a PAP) |
| + **Exportação Git** (fase posterior) | projeto final descarregável como repositório onde cada versão é um commit com autor = agente | extra |

Regras:
- `write_file` **nunca sobrescreve**: cria `artifact_versions` com `version_number+1`,
  `parent_version_id` = versão atual lida pelo agente.
- **Deteção de conflito:** se um agente escreve com base numa versão que já não é a
  atual (outro agente alterou entretanto), a escrita é rejeitada com a mensagem
  "o ficheiro mudou; lê a versão atual" → o agente faz `read_file` e integra.
  É um *optimistic locking* simples, e garante que ninguém apaga trabalho de outro
  silenciosamente.
- O espelho em disco (`workspaces/<project_id>/`) é regenerado a partir da BD; serve
  para download (ZIP) e, no futuro, para o sandbox de execução.

### 12.2 Decision Log — como nascem as decisões
1. **Planeamento**: o planner lista `open_questions` importantes.
2. **Durante a execução**: um agente usa `raise_decision`.
3. **Divergência na revisão**: autor discorda de um problema via `send_message`
   (máx. 1 troca) → se persistir, vira decisão.

Processo de uma decisão (`DecisionCoordinator`):
```
propostas em paralelo (cada agente: submit_proposal)
   → crítica cruzada (cada agente comenta a proposta do outro)
   → árbitro: agente configurado OU utilizador (intervenção CHOOSE_OPTION)
   → decisão + justificação registadas → injetadas no contexto de todas as tarefas seguintes
```

### 12.3 Human-in-the-loop

| Ação | Mecanismo |
|------|-----------|
| Pausar | flag no `RunManager`; o orquestrador verifica entre passos (pausa **cooperativa**: a chamada em curso termina). Estado `PAUSED`. |
| Retomar | limpa a flag, o loop continua a partir do estado na BD. |
| Cancelar | cancela a asyncio task (interrompe a chamada em curso); tarefas não terminadas → `CANCELLED`. |
| Aprovar/editar plano | intervenção `APPROVE_PLAN`; o run fica em `AWAITING_PLAN_APPROVAL`. |
| Editar tarefa | permitido em `PENDING`/`WAITING`; alteração registada como mensagem `SYSTEM`. |
| Instruções adicionais | mensagem `USER` (global ou dirigida a uma tarefa/agente); entra no contexto das chamadas seguintes. |
| Escolher opção | resposta a intervenção `CHOOSE_OPTION` → fecha a decisão com `decided_by = USER`. |
| Aprovar/rejeitar revisão | `human_override` na revisão. |

---

## 13. Experiências e métricas

### 13.1 Métricas recolhidas
- **Por chamada** (`llm_calls`): tokens de entrada/saída (quando a API os fornece —
  ambas fornecem, incluindo em streaming), latência, sucesso/erro, custo estimado.
- **Por execução** (`run_metrics`): `execution_time`, `api_calls`, `failed_calls`,
  `input_tokens`, `output_tokens`, `tasks_total/completed/failed`, `reviews`,
  `revisions`, `decisions`, `human_interventions`, `estimated_cost`, estado final.
- **Custo estimado** = tokens × preço por milhão definido em `pricing.py`/config.
  Os preços mudam; por isso são configuráveis e o valor é sempre apresentado como
  **estimativa**.

### 13.2 Metodologia das experiências
- Uma experiência = **o mesmo objetivo** × **várias estratégias** × **N repetições**
  (ex.: 3), porque os LLMs não são determinísticos: um só run não prova nada.
- Configuração guardada em snapshot em cada run (modelos, temperatura, limites) →
  reprodutibilidade e transparência.
- **Qualidade do resultado** (a métrica mais difícil) — combinamos:
  1. avaliação humana com rubrica (feita por ti, registada na aplicação, 1–5 por critério);
  2. verificações objetivas simples (ficheiros esperados existem, critérios de aceitação cumpridos);
  3. (fase futura) testes executados no sandbox.
  Evitamos usar um dos próprios modelos como juiz sem assinalar o enviesamento
  (um modelo pode favorecer respostas do seu estilo).
- A aplicação mostra médias e dispersão; **não tira conclusões por ti**.

### 13.3 Nota de honestidade para a PAP
Nenhum resultado é afirmado neste documento. A secção "Resultados" da documentação
só será escrita depois de corridas as experiências reais.

---

## 14. Segurança

| Tema | Medida |
|------|--------|
| API keys | Só em `.env` (fora do Git via `.gitignore`); `.env.example` sem valores; carregadas por `pydantic-settings`; nunca enviadas ao frontend nem guardadas na BD; nunca escritas em logs (máscara). |
| Autenticação | Passwords com hash argon2/bcrypt; token assinado em cookie `httpOnly`, `SameSite=Lax`, `Secure` em produção. |
| Autorização | Dependência FastAPI `get_project_for_user` usada em **todos** os endpoints de projeto; um utilizador não consegue sequer saber que projetos de outros existem (404). |
| Validação | Todos os inputs por Pydantic (tamanhos máximos: objetivo, instruções, nomes). Outputs dos LLMs também validados antes de tocar na BD. |
| Workspace | Caminhos normalizados; rejeita `..`, caminhos absolutos, symlinks, caracteres de controlo; lista de extensões permitidas; tamanho máx. por ficheiro e por projeto; nº máx. de ficheiros. |
| Prompt injection | O conteúdo gerado por um agente é **dados**, não instruções para o sistema. As ferramentas têm permissões mínimas (não há ferramenta de rede, shell ou execução). Um agente "convencido" por texto malicioso só consegue escrever ficheiros no workspace do projeto. |
| Custos / abuso | Limites por run (chamadas, tokens, custo, tempo) e nº máx. de runs simultâneos por utilizador. |
| Loops | Secção 9.4. |
| Execução de código | **Fora do MVP.** Código gerado nunca é executado no processo principal. Fase futura (opcional): contentor Docker descartável com `--network none`, utilizador não-root, CPU/memória/PIDs limitados, sistema de ficheiros só de leitura exceto `/tmp`, timeout, cópia do workspace (não montagem direta). |
| Frontend | React escapa HTML por defeito; conteúdo Markdown dos agentes renderizado sem HTML bruto; CORS restrito à origem do frontend. |

---

## 15. Riscos técnicos

| # | Risco | Prob. | Impacto | Mitigação |
|---|-------|-------|---------|-----------|
| R1 | Custo das APIs / limites dos planos gratuitos | Alta | Alto | Orçamento zero (DT-01): Ollama local + planos gratuitos; FakeProvider para 95% do desenvolvimento; limite de chamadas por run. |
| R1b | Modelos locais pequenos falham no tool calling | Alta | Alto | Modo de fallback com JSON validado (DT-01); escolher modelos com suporte a ferramentas. |
| R2 | Output estruturado inválido (JSON mal formado, campos em falta) | Média | Alto | Tool calling com esquema estrito + validação Pydantic + 1 retry com o erro. |
| R3 | Diferenças entre APIs no streaming com ferramentas | Média | Médio | Tipos `StreamEvent` normalizados; testes de contrato por provider. |
| R4 | Execuções longas (minutos) numa demo ao vivo | Alta | Alto | Tarefa de demo pequena; paralelismo; **replay** de um run real anterior (os eventos estão guardados — não é mockup, é histórico real). |
| R5 | Falha de rede / API em baixo no dia da defesa | Média | Muito alto | Plano B: run completo gravado previamente e reproduzível pela UI; screenshots/vídeo. |
| R6 | Rate limits (429) | Média | Médio | Retries com backoff; `max_parallel_tasks` baixo. |
| R7 | Contexto a crescer demasiado | Média | Médio | Resumos + orçamento de tokens (secção 11). |
| R8 | Revisões complacentes / "concordância" entre modelos | Alta | Médio | Rubrica, revisor de outro fornecedor, regra de severidade (10.3); é também um **resultado interessante** a observar. |
| R9 | Resultados experimentais pouco conclusivos (não determinismo) | Alta | Médio | Repetições, reportar dispersão, assumir limitações. |
| R10 | Crash do servidor a meio de um run | Baixa | Médio | Estado na BD; runs órfãos → `PAUSED` e retomáveis. |
| R11 | Âmbito demasiado grande para o tempo disponível | Alta | Muito alto | MVP em marcos (secção 17); cada fase termina com algo funcional. |
| R12 | Mudança de nomes de modelos / preços / SDKs | Média | Baixo | Modelos e preços em configuração; versões dos SDKs fixadas. |

---

## 16. Limitações assumidas

- Sem execução automática de código no MVP → os testes gerados pelos agentes são
  **revistos**, não executados.
- Um único processo de servidor (não escala horizontalmente — não é objetivo).
- A avaliação de qualidade tem componente subjetiva (humana).
- Os resultados dependem das versões dos modelos à data das experiências.
- Workspace orientado a ficheiros de texto (sem binários/imagens).
- Um utilizador por projeto no MVP (partilha fica desenhada, não implementada).
- Custos reais dependem dos preços em vigor; a aplicação mostra estimativas.

---

## 17. MVP

### Marco 1 — Núcleo demonstrável (o mínimo que prova a tese)
- Autenticação simples; CRUD de projetos; agentes ChatGPT e Claude configuráveis.
- Provider abstraction com OpenAI, Anthropic e Fake.
- Planner → DAG validado → execução respeitando dependências.
- Ferramentas de workspace com versionamento e deteção de conflito.
- Revisão cruzada com ciclo de correção e limite de rondas.
- Mensagens persistidas e streaming SSE.
- UI: Dashboard, Project Workspace, Agent Room (streaming), Task Board, File Viewer com histórico e diff.
- Pausar / cancelar.

### Marco 2 — PAP completa
- Decision Log com debate e escolha humana.
- Human-in-the-loop completo (aprovar plano, instruções, editar tarefa, override de revisão).
- Métricas por chamada e por run; página de métricas.
- Experiências (estratégias × repetições) com tabela e gráficos comparativos; exportação CSV.
- Replay de runs anteriores.

### Marco 3 — Extensões (se houver tempo)
- Exportação Git; download ZIP.
- Sandbox Docker para executar testes gerados.
- Terceiro provider (ex.: Gemini ou modelo local) — **ótima prova de extensibilidade na defesa**.
- Partilha de projetos entre utilizadores.

---

## 18. Roadmap por fases

A ordem segue a tua lista, com **uma alteração justificada**: o workspace (13) passa
para antes do orquestrador, porque o executor precisa de um sítio onde os agentes
escrevam os artefactos. As métricas nascem cedo (a tabela `llm_calls` é preenchida
desde a primeira chamada real) e a página de métricas vem depois.

Cada fase termina com: explicação → ficheiros → comandos → testes a passar → commit.

| Fase | Conteúdo | Critério de conclusão |
|------|----------|-----------------------|
| **0** | Requisitos + arquitetura (este documento) | Documento aprovado por ti |
| **1** | Estrutura do repositório, tooling (ruff, pytest, Vite, ESLint), `.env.example`, `docker-compose.yml` | `pytest` e `npm run build` correm (vazios) |
| **2** | Backend base: config, logging, erros, `/health` | `GET /health` responde; config lê `.env` |
| **3** | Base de dados: modelos, Alembic, PostgreSQL; autenticação | Migração cria todas as tabelas; login funciona (testes) |
| **4** | Provider abstraction + FakeProvider + registry + AgentRuntime + `llm_calls` | Testes de unidade do contrato com o Fake |
| **5** | OpenAIProvider (generate, stream, tools, usage) | Teste live opcional + endpoint "ping agent" |
| **6** | AnthropicProvider | Idem |
| **7** | Agentes (CRUD), mensagens, EventBus, endpoint SSE | Mensagem publicada aparece num cliente SSE |
| **8** | Workspace: artefactos, versões, diff, segurança de caminhos, ferramentas | Testes: versões, conflito, path traversal rejeitado |
| **9** | Tasks: modelo, DAG, scheduler, estados | Testes: ciclos rejeitados, ordem correta, paralelismo |
| **10** | Orquestrador: RunManager, Planner, Assigner, Executor, Guards, estratégias | Run completo com FakeProvider nos testes de integração |
| **11** | Review system | Integração: ciclo NEEDS_REVISION → APPROVED; limite de rondas respeitado |
| **12** | Decisões + human-in-the-loop | Integração: run pára em `WAITING_USER` e continua após resposta |
| **13** | Frontend (13a shell+auth+projetos · 13b Agent Room+Task Board · 13c Files+Decisions) | Demo end-to-end com APIs reais |
| **14** | Métricas: agregação + página | Valores batem certo com `llm_calls` |
| **15** | Experiências | Experiência com 2 estratégias × 2 repetições corre e compara |
| **16** | Testes finais, experiências reais, recolha de resultados | Resultados reais documentados |
| **17** | Polimento, documentação final, guião e plano B da demo | Ensaio completo da defesa |

### 18.3 Documentação da PAP (pasta `docs/`)
`00-analise-tecnica.md` (este), `01-requisitos.md`, `02-arquitetura.md`,
`03-tecnologias.md`, `04-modelo-dados.md`, `05-orquestrador.md`,
`06-comunicacao-agentes.md`, `07-revisao.md`, `08-seguranca.md`, `09-testes.md`,
`10-experiencias.md`, `11-limitacoes.md`, `12-resultados.md` (só no fim, com dados
reais), `decisoes-tecnicas.md` (registo das decisões de projeto e mudanças a este documento).

### Estratégia de testes (resumo)
- **Unitários**: DAG, scheduler, guards, segurança de caminhos, versionamento/diff,
  regras de revisão, context builder, parsing dos providers (com respostas gravadas).
- **Integração**: runs completos com FakeProvider programado (ex.: "o revisor pede
  revisão na 1.ª ronda e aprova na 2.ª") contra a BD de testes.
- **API**: endpoints com `httpx.AsyncClient`, incluindo autorização (utilizador B não
  acede ao projeto de A).
- **Live** (manuais, marcados, desligados por defeito): 1 chamada real por provider.
- **Frontend**: `tsc` + testes de componentes críticos; checklist E2E manual (e
  opcionalmente 1 teste Playwright do fluxo principal).

---

## 19. Estimativa de complexidade

Esforço em dias de trabalho focado (estimativa grosseira, para planeamento — não é compromisso).

| Componente | Complexidade | Esforço | Notas |
|------------|--------------|---------|-------|
| Estrutura, tooling, config | Baixa | 1 | |
| Base de dados + migrações + auth | Média | 2–3 | Muitas tabelas, mas padrão repetitivo |
| Provider abstraction + Fake | Média | 1–2 | O desenho dos tipos é o mais importante |
| OpenAIProvider (com streaming + tools) | Média-Alta | 2 | Streaming de tool calls é o ponto delicado |
| AnthropicProvider | Média-Alta | 2 | Idem |
| Agentes + mensagens + EventBus/SSE | Média | 2 | |
| Workspace + versionamento + segurança | Média | 2–3 | |
| Tasks + DAG + scheduler | Média | 1–2 | Algoritmos clássicos (Kahn) |
| **Orquestrador** (planner, executor, guards, estratégias) | **Muito alta** | 5–7 | Coração do sistema; mais iterações de prompts |
| **Sistema de revisão** | Alta | 2–3 | |
| Decisões + human-in-the-loop | Alta | 3–4 | Pausas e retomas exigem cuidado com estados |
| Frontend (7 páginas + streaming) | Alta | 7–10 | Maior volume de trabalho |
| Métricas | Baixa-Média | 1–2 | Dados já recolhidos desde a fase 4 |
| Experiências | Média | 2–3 | |
| Testes + experiências reais | Média | 3–5 | Inclui tempo de execução das experiências |
| Documentação + preparação da defesa | Média | 4–6 | |
| **Total aproximado** | | **~40–55 dias** | Sandbox de execução: +4–6 dias (Marco 3) |

---

## 20. Questões em aberto

Antes da Fase 1 convém definir:

1. **Prazo** da PAP e horas semanais disponíveis → ajusta o que entra nos Marcos 2/3.
2. **Orçamento para APIs** (ex.: 10 €, 20 €?) → define limites por defeito e modelos das experiências.
3. **Sistema operativo** onde vais desenvolver e fazer a demo, e se tens Docker instalado.
4. **Idioma da interface**: português, inglês, ou ambos?
5. Aprovação (ou alterações) às decisões principais: SSE em vez de WebSockets,
   sem Celery/Redis, BD como fonte de verdade do versionamento, sem frameworks de agentes.

### Respostas (Revisão 1)

| Questão | Resposta | Impacto |
|---------|----------|---------|
| Tempo | ~6 h/semana | DT-05 |
| Orçamento APIs | 0 € | DT-01 |
| Sistema | Windows 11 IoT Enterprise LTSC, sem Docker | DT-02, DT-03, DT-06 |
| Idioma | Português e inglês | DT-04 |
| Decisões | Aprovadas, com liberdade para ajustar | — |
