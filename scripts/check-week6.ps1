#Requires -Version 5.1
# Szybki smoke pod tydzień 5-6: health obu regionów + lista pokoi EU.
$ErrorActionPreference = "Stop"

function Probe([string]$Name, [string]$Url) {
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        $sw.Stop()
        Write-Host ("  {0,-8} OK  {1,5} ms  {2}" -f $Name, [int]$sw.ElapsedMilliseconds, $Url) -ForegroundColor Green
        return $true
    } catch {
        Write-Host ("  {0,-8} FAIL          {1}" -f $Name, $Url) -ForegroundColor Red
        return $false
    }
}

Write-Host "Week 5-6 smoke"
$ok = $true
$ok = (Probe "EU health" "http://localhost:8000/healthz") -and $ok
$ok = (Probe "EU front"  "http://localhost:3000/healthz") -and $ok
$ok = (Probe "chooser"   "http://127.0.0.1:3000/healthz") -and $ok

$us = Probe "US health" "http://localhost:8001/healthz"
if (-not $us) {
    Write-Host "  (US optional - run .\start-local.ps1 -Both)" -ForegroundColor Yellow
} else {
    $null = Probe "US front" "http://localhost:3001/healthz"
}

try {
    $rooms = Invoke-RestMethod "http://localhost:8000/rooms"
    Write-Host ("  EU rooms: {0}" -f $rooms.Count)
} catch {
    Write-Host "  EU rooms: unreachable" -ForegroundColor Red
    $ok = $false
}

Write-Host ""
Write-Host "Manual checks still needed:"
Write-Host "  1. open http://127.0.0.1:3000  (first visit -> faster region)"
Write-Host "  2. open http://127.0.0.1:3000/?propose=1  (Stay/Switch screenshot)"
Write-Host "  3. refresh regional host - region cookie must stick"
Write-Host "  4. IDENTITY: same mnemonic in EU and US -> two usernames"

if (-not $ok) { exit 1 }
