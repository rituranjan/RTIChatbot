Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path "$PSScriptRoot\.."

Write-Host "=== Backend setup ===" -ForegroundColor Cyan
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { py -m venv .venv }
& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
python manage.py makemigrations chatbot
python manage.py migrate

Write-Host "=== Frontend setup ===" -ForegroundColor Cyan
Set-Location "$root\frontend"
npm install

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Make sure Ollama is installed and models are pulled:"
Write-Host "  ollama pull qwen2.5:3b"
Write-Host "  ollama pull nomic-embed-text"
Write-Host ""
Write-Host "Start everything with:  scripts\run_windows.ps1"