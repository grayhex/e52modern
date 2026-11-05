# Docker Desktop (Linux containers). Preserves .env and all named volumes.
param([switch]$Emulator, [switch]$NoBuild, [switch]$Check)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Docker-Checked([string[]]$Arguments) {
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed. Check Docker Desktop and the configuration." }
}
Get-Command docker -ErrorAction Stop | Out-Null
Docker-Checked @('compose', 'version')
Docker-Checked @('info', '--format', '{{.ServerVersion}}')
if (-not $Check -and -not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
$compose = @('compose')
if ($Emulator) { $compose += @('--profile', 'emulator') }
Docker-Checked ($compose + @('config', '--quiet'))
if ($Check) { Write-Host 'Compose valid. No services, files or volumes changed.'; exit 0 }
$up = $compose + @('up', '-d')
if (-not $NoBuild) { $up += '--build' }
Docker-Checked $up
$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    & docker compose exec -T workbench python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('SYMPORT_HTTP_PORT','8765')+'/api/state', timeout=2).read()" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw 'Workbench is not ready. Inspect docker compose logs workbench.' }
Docker-Checked @('compose','exec','-T','workbench','python','-c',"import os; print('SymPort: http://127.0.0.1:'+os.getenv('SYMPORT_HTTP_PORT','8765'))")
