# Run Frontend for Solar & Wind Control Room
$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# Ensure Node and npm directory in PATH
$NodeDir = "C:\Users\satya\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.20.0-win-x64"
if (Test-Path $NodeDir) {
    $env:PATH = "$NodeDir;$env:PATH"
}

Write-Host "=== Starting Solar & Wind Control Room Frontend ===" -ForegroundColor Cyan

# Find npm executable
$NpmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $NpmCmd) {
    $fallbackNpm = Join-Path $NodeDir "npm.cmd"
    if (Test-Path $fallbackNpm) {
        $NpmExe = $fallbackNpm
    } else {
        Write-Error "npm was not found. Please ensure Node.js is installed."
    }
} else {
    $NpmExe = $NpmCmd.Source
}

if (-not (Test-Path (Join-Path $ScriptDir "node_modules"))) {
    Write-Host "Installing npm dependencies..." -ForegroundColor Yellow
    & $NpmExe install
}

Write-Host "Starting Next.js Dev Server at http://localhost:3000..." -ForegroundColor Green
& $NpmExe run dev
