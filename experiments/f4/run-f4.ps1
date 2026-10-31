#Requires -Version 5.1
<#
.SYNOPSIS
  One-shot F4 experiment: lab limits, venv, variant A+B, markdown report.

.EXAMPLE
  .\experiments\f4\run-f4.ps1
  .\experiments\f4\run-f4.ps1 -Users 6 -Pace 2
#>

param(
    [int]$Users = 4,
    [int]$Iterations = 3,
    [double]$Pace = 1.5,
    [int]$WsSamples = 5,
    [string]$Eu = "http://127.0.0.1:8000",
    [string]$Us = "http://127.0.0.1:8001",
    [switch]$SkipLimitPatch
)

$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
$Repo = (Resolve-Path (Join-Path $Here "..\..")).Path
Set-Location $Here

function Test-Health([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri "$Url/healthz" -UseBasicParsing -TimeoutSec 5
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

Write-Host "==> Health checks"
if (-not (Test-Health $Eu)) {
    throw "EU not healthy at $Eu/healthz — run .\start-local.ps1 -Both first"
}
if (-not (Test-Health $Us)) {
    throw "US not healthy at $Us/healthz — run .\start-local.ps1 -Both first"
}
Write-Host "  EU/US OK"

if (-not $SkipLimitPatch) {
    Write-Host "==> Lab rate limits"
    & (Join-Path $Here "prepare-lab-limits.ps1")
    Start-Sleep -Seconds 12
}

$venv = Join-Path $Here ".venv"
$py = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "==> Creating venv"
    python -m venv $venv
    & $py -m pip install --upgrade pip
    & $py -m pip install -r (Join-Path $Here "requirements.txt")
}

Write-Host "==> Running variants A + B"
& $py (Join-Path $Here "run.py") `
    --variant both `
    --eu $Eu `
    --us $Us `
    --users $Users `
    --iterations $Iterations `
    --pace $Pace `
    --ws-samples $WsSamples

if ($LASTEXITCODE -ne 0) {
    throw "F4 run failed"
}

Write-Host ""
Write-Host "Reports in experiments\f4\results\" -ForegroundColor Green
Write-Host "Repo root was: $Repo"
