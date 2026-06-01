param(
    [int]$Port = 8000,
    [switch]$SkipInstall,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $SkipInstall) {
    python -m pip install -e .[dev]
}

if (-not $SkipTests) {
    ruff check .
    pytest
}

New-Item -ItemType Directory -Force -Path ".local" | Out-Null
$env:AWA_PROVIDER_MODE = "mock"
$env:AWA_DATABASE_URL = "sqlite:///./.local/demo_workflow_assistant.db"
$env:AWA_APP_PORT = "$Port"

$baseUrl = "http://127.0.0.1:$Port"

Write-Host "Starting mock-mode reviewer app at $baseUrl"
$process = Start-Process -FilePath "python" `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port") `
    -WorkingDirectory $root `
    -PassThru `
    -WindowStyle Hidden

try {
    $ready = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri "$baseUrl/health" -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    if (-not $ready) {
        throw "Server did not become healthy at $baseUrl/health"
    }

    $env:AWA_DEMO_BASE_URL = $baseUrl
    python scripts/seed_demo.py

    Write-Host ""
    Write-Host "Reviewer demo is ready:"
    Write-Host "$baseUrl/"
    Write-Host "$baseUrl/queue"
    Write-Host ""
    Write-Host "Server PID: $($process.Id)"
    Write-Host "Stop it with: Stop-Process -Id $($process.Id)"
} catch {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
    throw
}
