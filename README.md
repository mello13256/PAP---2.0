# MultiMind

Plataforma de orquestração multiagente em que LLMs de fornecedores diferentes
(inicialmente OpenAI/ChatGPT e Anthropic/Claude) colaboram para resolver tarefas
complexas: planeiam, dividem o trabalho, produzem artefactos num workspace
partilhado e versionado, revêem o trabalho uns dos outros, corrigem e chegam a um
resultado final, com o histórico completo de mensagens, decisões e métricas.

Projeto desenvolvido no âmbito da PAP (Prova de Aptidão Profissional).

## Estado

| Fase | Conteúdo | Estado |
|------|----------|--------|
| 0 | Análise técnica ([`docs/00-analise-tecnica.md`](docs/00-analise-tecnica.md)) | ✅ |
| 1 | Estrutura e ferramentas | ✅ |
| 2 | Backend base (config, logging, erros) | ✅ |
| 3 | Base de dados (18 tabelas), autenticação, projetos | ✅ |
| 4 | Abstração de providers + AgentRuntime + métricas | ✅ |
| 5 | Provider compatível OpenAI (OpenAI, Ollama, GitHub Models, Gemini, Groq) | ✅ |
| 6 | Provider Anthropic | ✅ |
| 7 | Agentes, mensagens, eventos em tempo real | ✅ |
| 8 | Workspace partilhado e versionamento | ✅ |
| 9 | Tarefas e grafo de dependências | ✅ |
| 10 | Orquestrador (planear, atribuir, executar, limites) | ✅ |
| 11 | Sistema de revisão | ✅ |
| 13 | Interface web (PT/EN) | ✅ |
| 12 | Decisões e human-in-the-loop avançado | ⏳ |
| 14–15 | Métricas comparativas e experiências | ⏳ |

- Explicação de cada fase: [`docs/fases/`](docs/fases/)
- Decisões de projeto: [`docs/decisoes-tecnicas.md`](docs/decisoes-tecnicas.md)
- Instalação no Windows: [`docs/guia-instalacao-windows.md`](docs/guia-instalacao-windows.md)

## Arranque rápido (Windows)

**Duplo clique em `iniciar.cmd`**: prepara tudo e abre http://127.0.0.1:8000.

Ou, manualmente:

```powershell
copy .env.example .env
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload       # API em http://127.0.0.1:8000/docs
python -m app.cli providers         # providers configurados
python -m app.cli run "Cria uma app de inventário"   # os agentes a trabalhar
```

## Segurança

As API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) são lidas de variáveis de
ambiente / ficheiro `.env`, que **nunca** é incluído no Git.
