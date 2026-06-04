param(
    [int]$Port = 8000,
    [switch]$SkipInstall,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$localDir = if ($env:AWA_LOCAL_DIR) {
    $env:AWA_LOCAL_DIR
} else {
    Join-Path $root ".local"
}
New-Item -ItemType Directory -Force -Path $localDir | Out-Null

if (-not $env:RUFF_CACHE_DIR) {
    $env:RUFF_CACHE_DIR = Join-Path $localDir "ruff_cache"
}

if (-not $env:AWA_TEST_DB_PATH) {
    $env:AWA_TEST_DB_PATH = Join-Path $localDir "test_workflow_assistant.db"
}

function Assert-NativeSuccess {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

if (-not $SkipInstall) {
    python -m pip install -e .[dev]
    Assert-NativeSuccess "Install editable package"
}

if (-not $SkipTests) {
    ruff check .
    Assert-NativeSuccess "Run ruff"
    pytest -p no:cacheprovider
    Assert-NativeSuccess "Run pytest"
}

if (-not $env:AWA_PROVIDER_MODE) {
    $env:AWA_PROVIDER_MODE = "mock"
}

if (-not $env:AWA_DATABASE_URL) {
    $dbPath = Join-Path $localDir "demo_workflow_assistant.db"
    $dbUri = $dbPath -replace "\\", "/"
    $env:AWA_DATABASE_URL = "sqlite:///$dbUri"
}

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
    Assert-NativeSuccess "Seed demo requests"

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
