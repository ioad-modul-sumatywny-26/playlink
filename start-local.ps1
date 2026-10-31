#Requires -Version 5.1
<#
.SYNOPSIS
  Starts Playlink locally (no Cloudflare) and seeds demo data if rooms are empty.

.DESCRIPTION
  Uses the same regional recipe as production: deploy/deploy.sh via Git Bash.
  By default starts EU only. Pass -Both to also start the US stack on :3001/:8001.
  Seed runs only when GET /rooms returns an empty list - never wipes existing data.

.EXAMPLE
  .\start-local.ps1
  .\start-local.ps1 -Both
#>

param(
    [switch]$Both
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Find-Bash {
    $candidates = @(
        "C:\Program Files\Git\bin\bash.exe",
        "C:\Program Files\Git\usr\bin\bash.exe",
        (Get-Command bash -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
    ) | Where-Object { $_ -and (Test-Path $_) }
    if (-not $candidates) {
        throw "Git Bash not found. Install Git for Windows so deploy/deploy.sh can run."
    }
    return $candidates[0]
}

function Start-Region([string]$Bash, [string]$Region) {
    Write-Step "Starting region $Region (deploy/deploy.sh $Region)"
    & $Bash "deploy/deploy.sh" $Region
    if ($LASTEXITCODE -ne 0) {
        throw "deploy/deploy.sh $Region failed with exit $LASTEXITCODE"
    }
}

function Wait-Backend([string]$Url, [int]$Attempts = 60) {
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -eq 200) { return }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Backend did not become healthy: $Url"
}

function Invoke-Seed([string]$ApiBase, [string]$Project) {
    Write-Step "Seeding demo data on $ApiBase (skip if rooms already exist)"
    $seedScript = Join-Path $Root "scripts\seed_local.py"
    if (-not (Test-Path $seedScript)) {
        throw "Missing seed script: $seedScript"
    }

    # Seed from inside the region backend container (eth_account is available there).
    Get-Content -Raw $seedScript |
        docker compose -p $Project -f compose.yaml exec -T `
            -e PLAYLINK_BASE_URL=http://localhost:8000 `
            backend python -
    if ($LASTEXITCODE -ne 0) {
        throw "Seed failed for $ApiBase"
    }

    $sql = @"
UPDATE room
SET expires_at = NOW() + INTERVAL '7 days'
WHERE name IN ('q3-fragfest', 'd2-baal-runs', 'sc-broodwar');
"@
    docker compose -p $Project -f compose.yaml exec -T db `
        psql -U playlink -d playlink -c $sql | Out-Null
}

Write-Step "Checking Docker"
docker version --format "{{.Server.Version}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running. Start Docker Desktop and retry."
}
Write-Host "  Docker OK"

# Local mode: no PLAYLINK_DOMAIN / no tunnel. deploy.sh writes .run/<region>.env.
if (Test-Path (Join-Path $Root "deploy\site.env")) {
    Write-Host "  note: deploy/site.env exists - if PLAYLINK_DOMAIN is set this is public mode"
}

$bash = Find-Bash
Write-Host "  bash: $bash"

Start-Region $bash "eu"
if ($Both) {
    Start-Region $bash "us"
}

Write-Step "Waiting for EU backend health"
Wait-Backend "http://localhost:8000/healthz"
Write-Host "  EU backend healthy"

Invoke-Seed "http://localhost:8000" "playlink-eu"

Write-Host ""
Write-Host "Playlink is up (local mode, no Cloudflare)." -ForegroundColor Green
Write-Host "  Chooser : http://127.0.0.1:3000"
Write-Host "  EU app  : http://localhost:3000/rooms"
Write-Host "  EU API  : http://localhost:8000/docs"
if ($Both) {
    Write-Host "  US app  : http://localhost:3001/rooms"
    Write-Host "  US API  : http://localhost:8001/docs"
}
Write-Host ""
Write-Host "Demo login (IDENTITY) - paste this mnemonic:"
Write-Host "  test test test test test test test test test test test junk" -ForegroundColor Yellow
Write-Host ""
Write-Host "Stop EU:  docker compose -p playlink-eu -f compose.yaml down"
if ($Both) {
    Write-Host "Stop US:  docker compose -p playlink-us -f compose.yaml down"
}
Write-Host "Wipe DB:  add -v to the down command"
