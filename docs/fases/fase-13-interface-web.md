# Fase 13 — Interface web

## Arrancar

**Duplo clique em `iniciar.cmd`**, na raiz do projeto, ou no PowerShell:
```powershell
.\iniciar.ps1
```
O script prepara o backend, compila a interface, liga o servidor e abre
http://127.0.0.1:8000. Serve também depois de um `git pull`.

## Páginas

| Página | O que faz |
|--------|-----------|
| **Entrar / Criar conta** | Autenticação com cookie de sessão seguro (httpOnly). |
| **Painel** | Projetos, execuções recentes (com estado) e agentes ativos. |
| **Projeto** | Nova execução (objetivo, estratégia, agentes por ordem) · lista de execuções · ficheiros · exportar ZIP. |
| **Execução** | Quadro de tarefas, **sala dos agentes em tempo real**, controlos (pausar/retomar/cancelar), instruções para os agentes, ficheiros alterados, revisões, métricas e resultado final. |
| **Agentes** | Editar modelo (com lista de modelos instalados no Ollama), capacidades, instruções, temperatura; testar com um clique; criar agentes. |

Tudo em **português e inglês** (botão PT/EN).

## Tecnologias e porquê

| Tecnologia | Para quê |
|------------|----------|
| React + TypeScript + Vite | Interface por componentes, com tipos que espelham a API. |
| React Router | Navegação entre páginas (URL próprio por projeto e por execução). |
| TanStack Query | Cache dos dados da API, estados de carregamento e erro, e atualização quando chega um evento. |
| Tailwind CSS | Estilos consistentes sem escrever CSS de raiz. |
| EventSource (nativo) | Ligação SSE aos eventos do run; volta a ligar-se sozinha. |

Um só servidor: o FastAPI serve a API em `/api` e a interface compilada em `/`.
Não há CORS nem dois endereços. Em desenvolvimento pode usar-se `npm run dev`
(porta 5173, com proxy para a API).

## Como funciona o "ao vivo"

`hooks/useRunStream.ts` liga-se a `/api/runs/{id}/events`:
1. o servidor reenvia primeiro o histórico guardado (mensagens, ferramentas usadas);
2. depois envia os eventos novos à medida que acontecem;
3. `agent.started` + `agent.delta` constroem a "bolha" do agente a escrever;
   quando chega a mensagem final (com o mesmo `turn_id`), a bolha é substituída;
4. `task.updated`, `review.completed`, `file.changed`… atualizam o quadro, as
   revisões, as métricas e os ficheiros sem recarregar a página.

Abrir uma execução antiga mostra-a exatamente como aconteceu, porque o histórico
vem da BD.

## Verificação
Foi testado de ponta a ponta num browser real (Chromium, Playwright): registo →
projeto → iniciar → acompanhar ao vivo → resultado → ficheiros e diff → agentes
em inglês. Os agentes eram simulados por um servidor compatível com a API do Ollama.
