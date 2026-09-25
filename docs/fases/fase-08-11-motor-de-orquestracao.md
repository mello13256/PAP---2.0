# Fases 8 a 11 — Workspace, tarefas, orquestrador e revisão

Estas quatro fases formam o **motor** do MultiMind e foram feitas em conjunto.
Juntas permitem que os agentes trabalhem sozinhos, do objetivo ao resultado.

## Visão geral

```
objetivo ──► PLANNER ──► grafo de tarefas (DAG validado)
                              │
            ┌─────────────────┘  enquanto houver tarefas prontas:
            ▼
   atribuir (estratégia) ──► EXECUTAR (ferramentas) ──► REVER (outro agente)
                                   ▲                         │
                                   └──── NEEDS_REVISION ◄────┘ (máx. N rondas)
                                                             │ APPROVED
                                                             ▼
                                                        COMPLETED
            ... todas concluídas ──► RELATÓRIO FINAL ──► run COMPLETED
```

## Fase 8 — Workspace partilhado (`app/workspace/`)
- **Versões imutáveis**: escrever cria sempre uma versão nova, com autor (agente ou
  utilizador), tarefa, run, tipo (CREATE/MODIFY/REVISION) e resumo.
- **Bloqueio otimista**: quem escreve indica a versão em que se baseou. Se o ficheiro
  mudou entretanto → `409 workspace_conflict`. Nenhum agente apaga o trabalho de
  outro sem dar por isso.
- Conteúdo igual ao atual **não** cria versão (deteta "correções" vazias).
- **Caminhos seguros** (`paths.py`): sem `..`, sem caminhos absolutos, sem `.env`/`.git`,
  só extensões de texto conhecidas, limites de tamanho e de número de ficheiros.
- Espelho em disco em `workspaces/<projeto>/` (abre-se no VS Code) e exportação ZIP.
- API: `GET /files`, `/files/content`, `/files/history`, `/files/diff`, `PUT /files`, `/files/export`.

## Fase 9 — Tarefas (`app/tasks/`)
- `graph.py`: **algoritmo de Kahn** para validar que o plano é um DAG (sem ciclos) e
  obter uma ordem de execução.
- `state.py`: máquina de estados com transições permitidas
  (`PENDING → RUNNING → REVIEW → COMPLETED`, …).
- Tarefas "bloqueadas" (dependência falhou) são canceladas automaticamente.
- Dependências guardadas numa tabela N:N (`task_dependencies`), não em JSON.

## Fase 10 — Orquestrador (`app/orchestration/`)
| Ficheiro | Papel |
|----------|-------|
| `strategies.py` | Estratégias de colaboração (o que as experiências comparam). |
| `roles.py` | Quem planeia, executa, revê e sintetiza, segundo a estratégia. |
| `context.py` | Contexto do run, pausa cooperativa e **limites** (chamadas, tempo). |
| `tools.py` | Ferramentas dos agentes: `list_files`, `read_file`, `write_file`, `send_message`, `submit_*`. |
| `agent_loop.py` | Ciclo "modelo ↔ ferramentas" até à ferramenta terminal. |
| `context_builder.py` | A "memória": o que cada agente vê, com orçamento de caracteres. |
| `planner.py` | Objetivo → plano validado (com nova tentativa e plano de recurso). |
| `executor.py` | Execução de uma tarefa (ou correção). |
| `orchestrator.py` | Conduz o run inteiro e decide sempre o passo seguinte. |
| `run_manager.py` | Iniciar / pausar / retomar / cancelar; recuperação após reinício. |

**Estratégias disponíveis:** `collaborative`, `plan_implement_review`, `single`, `single_no_review`.

**Proteções contra ciclos infinitos:** máximo de passos por tarefa, de rondas de
revisão, de chamadas por run e de minutos por run. Deteção de "sem progresso" (a
correção não alterou nada). Nenhum agente decide continuar: só o orquestrador decide.

**Uma tarefa de cada vez**, de propósito: com 8 GB de VRAM só cabe um modelo de 8B
carregado. Correr tarefas em paralelo obrigaria a trocar constantemente de modelo.

## Fase 11 — Revisão (`orchestration/review.py`, `app/reviews/`)
- O revisor recebe a tarefa, os critérios, o conteúdo **e o diff** dos ficheiros, a
  revisão anterior e uma **rubrica** (correção, completude, coerência, qualidade, segurança).
- Resposta estruturada via `submit_review`: veredicto + problemas com severidade.
- **Regra de consistência**: se o revisor aponta um problema CRITICAL/MAJOR mas escreve
  APPROVED, o sistema trata como NEEDS_REVISION (e regista porquê).
- O autor recebe a revisão e produz uma nova versão (`REVISION`).

## Como experimentar (terminal)

```powershell
cd backend
git pull
python -m app.cli run "Cria uma pequena aplicação web para gerir o inventário de uma loja"
```
Opções: `--strategy plan_implement_review`, `--agents Qwen,Granite`, `--project "Loja"`.
No fim aparece a pasta com os ficheiros produzidos.

## Testes
`tests/integration/test_orchestrator.py` corre runs completos com agentes simulados.
Verifica o plano, a atribuição por capacidades, as versões, as revisões (incluindo
a regra de consistência), a paragem por falta de progresso, o plano de recurso, os
limites, pausa/retoma/cancelamento e as métricas.
