# Run Backend for Solar & Wind Control Room
$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "=== Starting Solar & Wind Control Room Backend ===" -ForegroundColor Cyan

# 1. Check virtualenv
$VenvPy = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    & .venv\Scripts\pip.exe install -r requirements.txt
}

# 2. Check bundled datasets
$BundledSolar = Join-Path $ScriptDir "data\bundled\solar_generation_sample.csv"
if (-not (Test-Path $BundledSolar)) {
    Write-Host "Generating Kaggle-aligned sample datasets..." -ForegroundColor Yellow
    & $VenvPy data\generate_bundled_data.py
}

# 3. Launch FastAPI backend
$env:PYTHONPATH = $ScriptDir
Write-Host "Starting FastAPI application at http://127.0.0.1:8000..." -ForegroundColor Green
& $VenvPy -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
