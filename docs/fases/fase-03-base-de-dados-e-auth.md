# Fase 3 — Base de dados, migrações, autenticação e projetos

## O que foi feito

| Ficheiro / pasta | Responsabilidade |
|------------------|------------------|
| `app/db/base.py` | Base declarativa, convenção de nomes das constraints, mixins `id`/`created_at`. |
| `app/db/types.py` | `UTCDateTime` (datas sempre em UTC) e `enum_column` (enums portáveis com `CHECK`). |
| `app/db/session.py` | Motor assíncrono, *pragmas* do SQLite, uma sessão por pedido. |
| `app/*/models.py` | **18 tabelas**: o modelo de dados completo da secção 6 da análise. |
| `alembic/` | Migrações. A migração inicial foi **gerada automaticamente** a partir dos modelos. |
| `app/auth/` | Registo, login, logout, `me`; hash argon2; sessão em cookie `httpOnly`. |
| `app/projects/` | CRUD de projetos com **autorização por projeto**. |

## Porque criar já as 18 tabelas?
O modelo de dados é o "contrato" de toda a aplicação. Defini-lo por inteiro no início
obriga a pensar nas relações entre tudo (runs, tarefas, versões, revisões…) antes de
programar a lógica. As fases seguintes podem ajustá-lo com novas migrações.

## Conceitos para a defesa

**Migrações (Alembic).** O esquema da BD evolui como o código: cada alteração é um
ficheiro versionado em `alembic/versions/`. A aplicação aplica as migrações pendentes
ao arrancar (`AUTO_MIGRATE=true`). Há um teste que garante que as migrações e os
modelos descrevem **exatamente** o mesmo esquema.

**Pragmas do SQLite** (`session.py`):
- `journal_mode=WAL`: leituras e escrita em simultâneo;
- `foreign_keys=ON`: no SQLite as chaves estrangeiras vêm **desligadas** por defeito!
- `busy_timeout=5000`: espera em vez de falhar se a BD estiver ocupada.

**Passwords.** Guardamos só o hash **argon2**, um algoritmo lento de propósito, que
torna muito caro testar milhões de passwords. No login, se o email não existir,
verificamos na mesma contra um hash falso. Assim o tempo de resposta não revela
quais emails estão registados.

**Sessão.** Depois do login, o servidor envia um token JWT assinado com a
`SECRET_KEY` num cookie:
- `httpOnly`: o JavaScript da página não o consegue ler (protege contra XSS);
- `SameSite=Lax`: não é enviado em formulários de outros sites (protege contra CSRF);
- `Secure` em produção: só por HTTPS.

**Autorização por projeto.** Todos os endpoints de projeto passam pela dependência
`get_owned_project`. Se o projeto não existir **ou** pertencer a outro utilizador, a
resposta é a mesma: `404`. Não se revela que o projeto existe.

**Arquivar em vez de apagar.** `DELETE /projects/{id}` arquiva o projeto e preserva
o histórico (runs, versões, decisões).

## Como verificar
```powershell
cd backend
pytest                           # 21 testes
uvicorn app.main:app --reload    # cria/atualiza backend/data/multimind.db
```
Em http://127.0.0.1:8000/docs podes experimentar `POST /api/auth/register` e
`POST /api/projects` diretamente no browser.

Para ver as tabelas criadas podes usar o "DB Browser for SQLite" (gratuito) e abrir
`backend/data/multimind.db`.
