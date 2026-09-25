# MultiMind — arranque com um só comando (Windows / PowerShell)
#
#   .\iniciar.ps1          prepara tudo, liga o servidor e abre o browser
#
# Faz sempre o mesmo, por isso também serve depois de um "git pull":
#   1. cria/atualiza o ambiente Python do backend
#   2. compila a interface web (frontend)
#   3. liga o servidor em http://127.0.0.1:8000 e abre o browser

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

Step 'Backend: ambiente Python e dependências'
Set-Location "$root\backend"
if (-not (Test-Path '.venv')) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check -e '.[dev]'

Step 'Frontend: dependências e compilação da interface'
Set-Location "$root\frontend"
npm install --no-audit --no-fund --loglevel=error
if ($LASTEXITCODE -ne 0) { throw 'npm install falhou' }
npm run build --silent
if ($LASTEXITCODE -ne 0) { throw 'A compilação da interface falhou' }

Step 'A ligar o MultiMind em http://127.0.0.1:8000  (Ctrl+C para parar)'
Set-Location "$root\backend"
# Abre o browser daqui a 3 segundos, quando o servidor já estiver a responder.
Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', 'Start-Sleep 3; Start-Process http://127.0.0.1:8000'
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
