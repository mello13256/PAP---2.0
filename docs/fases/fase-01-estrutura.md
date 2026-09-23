# Fase 1 — Estrutura do repositório e ferramentas

## O que foi feito
- `backend/` — pacote Python `app` com `pyproject.toml` (dependências e configuração
  das ferramentas num único ficheiro).
- `frontend/` — projeto React + TypeScript criado com Vite, limpo do código de exemplo.
- `.env.example` — lista de todas as variáveis de configuração, **sem valores reais**.
- `.gitignore` — exclui `.env`, ambientes virtuais, `node_modules`, workspaces e a BD local.
- Guia de instalação para Windows.

## Ferramentas e porquê

| Ferramenta | Função |
|------------|--------|
| `venv` + `pip` | Ambiente isolado de dependências Python (padrão, sem instalar nada extra). |
| `pytest` (+ `pytest-asyncio`) | Testes automáticos, incluindo código assíncrono. |
| `ruff` | Linter + formatador numa só ferramenta. |
| Vite | Servidor de desenvolvimento e build do frontend. |
| `tsc` | Verificação de tipos TypeScript (`strict`). |
| `oxlint` | Linter do frontend (vem com o template atual do Vite). |

## Decisão: proxy `/api` no Vite
Em desenvolvimento o frontend corre em `:5173` e o backend em `:8000`. O Vite
reencaminha `/api/*` para o backend, por isso o browser fala com **uma única origem**.
Assim os cookies de sessão funcionam sem configuração extra e não há problemas de CORS.

## Como verificar
```powershell
cd backend;  pytest;  ruff check .
cd frontend; npm run build; npm run lint
```
