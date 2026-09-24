# Fase 7 — Agentes, execuções, mensagens e eventos em tempo real

## O que foi feito

| Módulo | Endpoints / responsabilidade |
|--------|------------------------------|
| `agents/` | `GET/POST /api/agents`, `GET/PATCH/DELETE /api/agents/{id}`, `POST /api/agents/{id}/ping`, `POST /api/agents/defaults`, `GET /api/providers`, `GET /api/providers/{key}/models` |
| `agents/defaults.py` | Cada utilizador novo recebe **Granite** (Ollama), **Qwen** (Ollama) e **Simulado** (desativado). |
| `agents/factory.py` | `RuntimeFactory`: agente da BD → `AgentRuntime`. É o único sítio que resolve a chave de provider. |
| `runs/` | `POST/GET /api/projects/{id}/runs`, `GET /api/runs/{id}`, **`GET /api/runs/{id}/events` (SSE)** |
| `messages/` | `GET/POST /api/runs/{id}/messages`, **`POST /api/runs/{id}/ask`** (dar a palavra a um agente) |
| `events/bus.py` | `EventBus`: publica eventos persistentes e transitórios. |
| `events/sse.py` | Formato SSE, replay dos eventos guardados e streaming ao vivo. |
| `orchestration/conversation.py` | `agent_turn`: um agente lê a conversa do run e responde em streaming. |
| `core/background.py` | Tarefas em segundo plano com registo de erros. |

## Comunicação entre agentes: como funciona

```
POST /runs/{id}/ask {agent: Granite, prompt: "Que arquitetura usar?"}
   │ 1. guarda a pergunta (mensagem USER)                   ──► evento message.created
   │ 2. responde 202 logo; o trabalho continua em segundo plano
   ▼
agent_turn(Granite)
   │ 3. lê as últimas mensagens do run e monta a conversa:
   │      [Utilizador]: Que arquitetura usar?
   │ 4. chama o modelo em streaming                          ──► agent.started
   │      "Analis" "ei a ta" "refa…"                         ──► agent.delta (vários)
   │ 5. guarda a resposta completa (mensagem AGENT)          ──► message.created
   ▼
POST /runs/{id}/ask {agent: Qwen}
   │    a conversa já inclui [Granite]: Analisei a tarefa…
   ▼    o Qwen responde ao Granite, **através do sistema**
```

Os agentes nunca comunicam diretamente: tudo passa pelo sistema (padrão
**Mediator**), que guarda, numera e transmite cada mensagem. O teste
`test_agents_talk_through_the_orchestrator` verifica que o Qwen recebe
realmente o que o Granite disse.

## Eventos persistentes vs. transitórios

| Tipo | Exemplo | Guardado? | Porquê |
|------|---------|-----------|--------|
| Persistente | `run.created`, `message.created` | Sim, em `run_events`, com id sequencial | Recuperar após falha de ligação; rever execuções antigas |
| Transitório | `agent.delta` (fragmentos de texto) | Não | Seriam milhares de linhas; a mensagem final fica em `messages` |

**Retoma da ligação.** O browser guarda o último `id` recebido. Se a ligação cair,
reenvia-o no cabeçalho `Last-Event-ID` e o servidor manda só o que faltou.

**Subscrever antes de ler.** O stream subscreve os eventos novos **antes** de ler os
guardados. Caso contrário, um evento publicado entre as duas operações perdia-se.
Os duplicados são descartados pelo id.

**Cliente lento.** Se um browser não consumir os eventos a tempo e a fila encher, a
ligação é terminada. O browser volta a ligar-se e recupera os eventos persistentes.
A memória do servidor não cresce sem limite.

## Agentes desativados, não apagados
`DELETE /api/agents/{id}` desativa o agente. As mensagens e versões antigas
continuam a indicar quem as escreveu.

## Como verificar

```powershell
cd backend; pytest        # 106 testes
uvicorn app.main:app --reload
```
Em http://127.0.0.1:8000/docs:
1. `GET /api/agents`: se a tua conta foi criada antes desta fase, corre primeiro
   `POST /api/agents/defaults`.
2. `POST /api/agents/{id}/ping` com o id do Granite: chamada real ao Ollama.
3. `POST /api/projects/{id}/runs` com `{"objective": "App de inventário"}`.
4. Abre noutro separador `http://127.0.0.1:8000/api/runs/<run_id>/events`.
5. `POST /api/runs/{run_id}/ask` com `{"agent_id": "<Granite>", "prompt": "Que arquitetura usar?"}`
   e observa o separador dos eventos. Depois repete com o Qwen, sem `prompt`.
6. `GET /api/runs/{run_id}/messages`: a conversa completa guardada.
