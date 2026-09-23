# Fase 2 — Backend base

## O que foi feito

| Ficheiro | Responsabilidade |
|----------|------------------|
| `app/core/config.py` | Lê a configuração do `.env` / variáveis de ambiente, com validação (Pydantic Settings). |
| `app/core/logging.py` | Logging com um **filtro que oculta segredos** (`***`). |
| `app/core/errors.py` | Exceções da aplicação (`NotFoundError`, `ConflictError`, …) e conversão para JSON. |
| `app/api/health.py` | `GET /api/health`: verificação de que o servidor está vivo. |
| `app/main.py` | `create_app(settings)`: *factory* que monta a aplicação. |

## Conceitos para a defesa

**Factory `create_app`.** A aplicação é construída por uma função que recebe a
configuração. Nos testes criamos aplicações isoladas, cada uma com a sua BD
temporária, sem tocar nos dados reais.

**`SecretStr`.** As API keys são guardadas num tipo que esconde o valor em `print`,
`repr` e logs. Para usar a chave é preciso chamar explicitamente `.get_secret_value()`.

**Defesa em profundidade nos logs.** Mesmo que um erro de uma biblioteca inclua a
chave, o filtro de logging substitui-a antes de ser escrita.

**Erros consistentes.** Os serviços lançam `NotFoundError("Projeto não encontrado")`
sem saber nada de HTTP. Um único handler transforma isso em
`404 {"error": {"code": "not_found", "message": "..."}}`. O frontend trata todos os
erros da mesma forma.

**`SECRET_KEY`.** Obrigatória em produção. Em desenvolvimento, se faltar, é gerada
uma temporária e aparece um aviso no arranque.

## Como verificar
```powershell
cd backend
pytest
uvicorn app.main:app --reload
# abrir http://127.0.0.1:8000/api/health e http://127.0.0.1:8000/docs
```
