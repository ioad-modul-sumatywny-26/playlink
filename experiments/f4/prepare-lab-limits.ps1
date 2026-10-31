#Requires -Version 5.1
<#
.SYNOPSIS
  Raises backend rate limits in local .run env files and recreates backends.

.DESCRIPTION
  Default Playlink limit is 10/minute — too low for F4. This patches
  .run/eu.env and .run/us.env (if present) then recreates backend containers.
#>

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root

function Set-Limit([string]$EnvFile) {
    if (-not (Test-Path $EnvFile)) {
        Write-Host "  skip missing $EnvFile"
        return
    }
    $raw = Get-Content $EnvFile -Raw
    if ($raw -match '(?m)^DEFAULT_RATE_LIMIT=') {
        $raw = [regex]::Replace($raw, '(?m)^DEFAULT_RATE_LIMIT=.*$', 'DEFAULT_RATE_LIMIT=1000/minute')
    } else {
        $raw = $raw.TrimEnd() + "`nDEFAULT_RATE_LIMIT=1000/minute`n"
    }
    if ($raw -match '(?m)^WS_RATE_LIMIT_MAX_MESSAGES=') {
        $raw = [regex]::Replace($raw, '(?m)^WS_RATE_LIMIT_MAX_MESSAGES=.*$', 'WS_RATE_LIMIT_MAX_MESSAGES=100')
    } else {
        $raw = $raw.TrimEnd() + "`nWS_RATE_LIMIT_MAX_MESSAGES=100`n"
    }
    Set-Content -Path $EnvFile -Value $raw -NoNewline
    Write-Host "  patched $EnvFile"
}

Write-Host "==> Preparing lab rate limits"
Set-Limit (Join-Path $Root ".run\eu.env")
Set-Limit (Join-Path $Root ".run\us.env")

foreach ($region in @("eu", "us")) {
    $proj = "playlink-$region"
    $env:APP_ENV_FILE = ".run/$region.env"
    $env:IMAGE_TAG = "local"
    if ($region -eq "eu") {
        $env:FRONTEND_PORT = "3000"
        $env:BACKEND_PORT = "8000"
    } else {
        $env:FRONTEND_PORT = "3001"
        $env:BACKEND_PORT = "8001"
    }

    if (-not (Test-Path (Join-Path $Root ".run\$region.env"))) {
        Write-Host "  skip $proj — no .run/$region.env (run start-local first)"
        continue
    }

    $running = docker compose -p $proj -f compose.yaml ps -q backend 2>$null
    if ($running) {
        Write-Host "==> Recreating $proj backend"
        docker compose -p $proj -f compose.yaml -f compose.build.yaml -f compose.ports.yaml up -d --no-deps --force-recreate backend
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to recreate backend for $region"
        }
    } else {
        Write-Host "  $proj backend not running — limits will apply on next deploy"
    }
}

Write-Host "Done. Wait ~10s for health, then run the experiment."
