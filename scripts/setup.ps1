# BharatQuant — one-shot Windows setup script
# Run from PowerShell at the project root:
#   .\scripts\setup.ps1

$ErrorActionPreference = "Stop"

Write-Host "==> BharatQuant setup (Windows / PowerShell)" -ForegroundColor Cyan

# 1. Backend
Write-Host "`n[1/3] Backend: creating venv and installing requirements..." -ForegroundColor Yellow
Push-Location backend
if (-not (Test-Path .venv)) {
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created backend/.env from example" -ForegroundColor Green
}
Pop-Location

# 2. Frontend
Write-Host "`n[2/3] Frontend: installing npm dependencies..." -ForegroundColor Yellow
Push-Location frontend
npm install --legacy-peer-deps
if (-not (Test-Path .env.local)) {
    Copy-Item .env.local.example .env.local
    Write-Host "Created frontend/.env.local from example" -ForegroundColor Green
}
Pop-Location

# 3. Ollama models
Write-Host "`n[3/3] Pulling local LLM models (Ollama)..." -ForegroundColor Yellow
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($null -eq $ollama) {
    Write-Host "  Ollama not found. Install from https://ollama.com/download" -ForegroundColor Red
} else {
    ollama pull llama3
    ollama pull nomic-embed-text
    Write-Host "  Ollama models ready." -ForegroundColor Green
}

Write-Host "`n[ok] Setup complete." -ForegroundColor Cyan
Write-Host "Run:`n  cd backend; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload" -ForegroundColor Cyan
Write-Host "Then in another terminal:`n  cd frontend; npm run dev" -ForegroundColor Cyan
