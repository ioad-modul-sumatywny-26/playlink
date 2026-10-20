#Requires -Version 5.1
<#
.SYNOPSIS
  Starts Playlink locally with Docker and seeds demo data if the DB is empty.

.DESCRIPTION
  - Ensures .env files exist
  - Starts docker compose (db + backend + frontend)
  - Waits for backend health
  - Seeds a demo user + sample rooms ONLY when /rooms is empty
  - Never wipes existing data

.EXAMPLE
  .\start-local.ps1
#>

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Ensure-EnvFile([string]$Example, [string]$Target) {
    if (Test-Path $Target) {
        Write-Host "  keep existing $Target"
        return
    }
    if (-not (Test-Path $Example)) {
        throw "Missing example env file: $Example"
    }
    Copy-Item $Example $Target
    Write-Host "  created $Target from $(Split-Path $Example -Leaf)"
}

Write-Step "Checking Docker"
docker version --format "{{.Server.Version}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running. Start Docker Desktop and retry."
}
Write-Host "  Docker OK"

Write-Step "Preparing env files"
Ensure-EnvFile (Join-Path $Root ".env.example") (Join-Path $Root ".env")
Ensure-EnvFile (Join-Path $Root "frontend\.env.example") (Join-Path $Root "frontend\.env")

Write-Step "Starting stack (docker compose up --build -d)"
docker compose up --build -d
if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed"
}

Write-Step "Waiting for backend health"
$ready = $false
for ($i = 1; $i -le 60; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/" -UseBasicParsing -TimeoutSec 3
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $ready) {
    throw "Backend did not become healthy in time. Check: docker compose logs backend"
}
Write-Host "  backend healthy"

Write-Step "Seeding demo data (skip if rooms already exist)"
$seedScript = Join-Path $Root "scripts\seed_local.py"
if (-not (Test-Path $seedScript)) {
    throw "Missing seed script: $seedScript"
}

# Run inside the backend container so eth_account is available.
# localhost:8000 — same container that serves the API.
Get-Content -Raw $seedScript |
    docker compose exec -T `
        -e PLAYLINK_BASE_URL=http://localhost:8000 `
        backend python -
if ($LASTEXITCODE -ne 0) {
    throw "Seed failed"
}

# Extend TTL of known demo rooms (no-op if they were not created this run).
Write-Step "Extending demo room TTL (7 days), if present"
$envFile = Join-Path $Root ".env"
$pgUser = "postgres"
$pgDb = "playlink"
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*POSTGRES_USER=(.+)$') { $pgUser = $Matches[1].Trim() }
    if ($_ -match '^\s*POSTGRES_DB=(.+)$') { $pgDb = $Matches[1].Trim() }
}
$sql = @"
UPDATE room
SET expires_at = NOW() + INTERVAL '7 days'
WHERE name IN ('q3-fragfest', 'd2-baal-runs', 'sc-broodwar');
"@
docker compose exec -T db psql -U $pgUser -d $pgDb -c $sql | Out-Null

Write-Host ""
Write-Host "Playlink is up." -ForegroundColor Green
Write-Host "  Frontend : http://localhost:3000"
Write-Host "  Rooms    : http://localhost:3000/rooms"
Write-Host "  Backend  : http://localhost:8000/docs"
Write-Host ""
Write-Host "Demo login (IDENTITY page) - paste this mnemonic:"
Write-Host "  test test test test test test test test test test test junk" -ForegroundColor Yellow
Write-Host ""
Write-Host "Stop with:  docker compose down"
Write-Host "Wipe DB:    docker compose down -v"
