# Aplicação de ambiente de trabalho (MultiMind.exe) e gestor de modelos

## Objetivo
Qualquer pessoa pode usar o MultiMind **sem instalar Python, Node, nem abrir terminais**,
e **sem internet** (depois de os modelos estarem descarregados).

## Como se usa
1. Instalar o **Ollama** (https://ollama.com). Só é preciso internet uma vez.
2. Descarregar o **MultiMind.exe** da página de releases (`latest-build`) e fazer duplo clique.
3. Na página **Modelos**, carregar em **Descarregar** nos modelos recomendados
   (Granite e Qwen). Aparece uma barra de progresso.
4. Criar um projeto, escrever o objetivo e **Iniciar MultiMind**.

A pequena janela "MultiMind" tem os botões **Abrir MultiMind**, **Pasta de dados** e
**Sair**, e mostra se o Ollama está a correr.

## Como funciona o .exe

```
MultiMind.exe (PyInstaller, um só ficheiro)
 ├── Python + todas as bibliotecas (FastAPI, SQLAlchemy, SDKs, ...)
 ├── código do MultiMind (app/)
 ├── recursos: migrações (alembic/), preços, interface compilada (frontend_dist/)
 └── desktop.py:
       1. prepara %LOCALAPPDATA%\MultiMind (BD, workspaces, logs, chave de sessão)
       2. aplica as migrações
       3. liga o servidor em 127.0.0.1 (só acessível no próprio PC)
       4. abre o browser e a janela de controlo
```

- **Recursos vs. dados** (`app/core/paths.py`): os recursos vêm dentro do .exe (só
  leitura); os dados ficam em `%LOCALAPPDATA%\MultiMind` e sobrevivem a atualizações.
- **Uma só instância**: se o MultiMind já estiver aberto, abrir o .exe outra vez só
  abre o browser.
- **Porta ocupada**: se a 8000 estiver ocupada por outro programa, escolhe outra livre.
- **Sem consola**: os registos vão para `%LOCALAPPDATA%\MultiMind\logs\multimind.log`.
- **Chaves de API** (opcional): um ficheiro `.env` na pasta de dados.

## Compilação automática (GitHub Actions)
`.github/workflows/windows-exe.yml` corre num **Windows real** a cada alteração:
1. corre os testes do backend em Windows;
2. compila a interface (`npm ci && npm run build`);
3. compila o `.exe` com o PyInstaller (`backend/packaging/multimind.spec`);
4. **testa o .exe** (`--smoke-test`: arranca, verifica que a API e a interface
   respondem e termina);
5. publica-o na release `latest-build`.

Compilar à mão (no Windows, na pasta `backend`, com o `.venv` ativo):
```powershell
pip install -e ".[desktop]"
cd ..\frontend; npm run build; cd ..\backend
pyinstaller packaging\multimind.spec --noconfirm   # → dist\MultiMind.exe
```

## Gestor de modelos (`app/models_manager/`)
Usa a API nativa do Ollama:

| Ação | Ollama | MultiMind |
|------|--------|-----------|
| Está a correr? | `GET /api/version` | `GET /api/models/status` |
| Instalados | `GET /api/tags` | idem |
| Descarregar | `POST /api/pull` (progresso em linhas JSON) | `POST /api/models/pull` + `GET /api/models/pulls` |
| Remover | `DELETE /api/delete` | `DELETE /api/models/{nome}` |

O download corre em segundo plano. O progresso é a soma das "camadas" do modelo, e a
interface pergunta-o a cada segundo enquanto houver downloads ativos. Os nomes dos
modelos são validados (não é possível injetar caminhos ou comandos).

## Ícone
Gerado por código (`packaging/make_icon.py`, sem bibliotecas externas): três nós
ligados, que representam agentes a colaborar.
