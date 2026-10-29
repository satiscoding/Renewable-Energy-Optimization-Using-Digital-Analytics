# Solar & Wind Control Room - Unified PowerShell Launcher
$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $RootDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   SOLAR & WIND CONTROL ROOM - MULTI-SITE PLATFORM        " -ForegroundColor Cyan
Write-Host "   Phase-II Capstone Implementation                       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Start Backend in separate window
Write-Host "Launching Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
$BackendScript = Join-Path $RootDir "backend\run_backend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$BackendScript`""

Start-Sleep -Seconds 3

# 2. Start Frontend in separate window
Write-Host "Launching Frontend on http://localhost:3000..." -ForegroundColor Yellow
$FrontendScript = Join-Path $RootDir "frontend\run_frontend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$FrontendScript`""

Write-Host ""
Write-Host "System initialized successfully!" -ForegroundColor Green
Write-Host "Control Room UI: http://localhost:3000" -ForegroundColor White
Write-Host "FastAPI Docs:    http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan
