# Guia de instalação — Windows 11 (incluindo LTSC)

As edições LTSC não têm a Microsoft Store e podem não ter o `winget`.
Por isso usamos sempre os **instaladores oficiais**.

## 1. Programas necessários (uma vez)

| Programa | Onde | Notas |
|----------|------|-------|
| **Python 3.12** (ou 3.11+) | https://www.python.org/downloads/windows/ | No instalador, marca **"Add python.exe to PATH"**. |
| **Node.js LTS** | https://nodejs.org | Instalador `.msi`, opções por defeito. |
| **Git** | https://git-scm.com/download/win | Opções por defeito. |
| **VS Code** (recomendado) | https://code.visualstudio.com | Extensões: Python, ESLint. |
| **Ollama** (para modelos locais) | https://ollama.com/download/windows | Só é preciso a partir da fase dos providers. |

Confirma num **PowerShell** novo:

```powershell
python --version
node --version
git --version
```

Se o PowerShell recusar ativar o ambiente virtual ("running scripts is disabled"),
corre uma vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 2. Obter o projeto

```powershell
git clone https://github.com/mello13256/PAP---2.0.git
cd PAP---2.0
git checkout claude/multimind-multiagent-platform-b4ux80
copy .env.example .env
```

## 3. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Para arrancar o servidor (a partir da Fase 2):

```powershell
uvicorn app.main:app --reload
```

A documentação automática da API fica em http://127.0.0.1:8000/docs

## 4. Frontend (noutro terminal)

```powershell
cd frontend
npm install
npm run dev
```

Abre http://localhost:5173

## 5. Modelos locais com Ollama (fase dos providers)

```powershell
ollama pull granite3.3:2b     # exemplo; o tamanho depende da RAM do PC
ollama list
```

O nome exato dos modelos disponíveis está em https://ollama.com/library
(procura "granite").
