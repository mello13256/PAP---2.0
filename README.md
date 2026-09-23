# MultiMind

Plataforma de orquestração multiagente em que LLMs de fornecedores diferentes
(inicialmente OpenAI/ChatGPT e Anthropic/Claude) colaboram para resolver tarefas
complexas: planeiam, dividem o trabalho, produzem artefactos num workspace
partilhado e versionado, revêem o trabalho uns dos outros, corrigem e chegam a um
resultado final, com o histórico completo de mensagens, decisões e métricas.

Projeto desenvolvido no âmbito da PAP (Prova de Aptidão Profissional).

## Estado

**Fase 0 — Análise técnica.** Ver [`docs/00-analise-tecnica.md`](docs/00-analise-tecnica.md).

## Segurança

As API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) são lidas de variáveis de
ambiente / ficheiro `.env`, que **nunca** é incluído no Git.
