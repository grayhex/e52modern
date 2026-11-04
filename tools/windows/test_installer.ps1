# CI test of the real installer: fresh install, upgrade over a running copy (the update path),
# data preservation and uninstall. Windows only. Usage: test_installer.ps1 -Old old.exe -New new.exe
param([Parameter(Mandatory)][string]$Old, [Parameter(Mandatory)][string]$New, [Parameter(Mandatory)][string]$NewVersion)
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:RUNNER_TEMP 'bridge-installer-test'
$dir = Join-Path $root 'app'
$data = Join-Path $env:LOCALAPPDATA 'SymPortBridge'
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{8F3C2B7A-5D41-4C0E-9B6A-7E52A1F0C3D9}_is1'
New-Item -ItemType Directory -Force $root | Out-Null

function Run([string]$exe, [string[]]$arguments) {
    $p = Start-Process -FilePath $exe -ArgumentList $arguments -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "$exe exited with $($p.ExitCode)" }
}
function Assert([bool]$condition, [string]$message) { if (-not $condition) { throw "FAILED: $message" } }
function Version() { (Get-ItemProperty $uninstallKey).DisplayVersion }

# 1. Fresh silent install of the old version: no administrator rights, no prompts.
Run $Old @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=$dir", "/LOG=$root\old.log", '/TASKS=autostart')
Assert (Test-Path "$dir\SymPortBridge.exe") 'exe installed'
Assert (Test-Path "$dir\LICENSE.txt") 'license installed'
Assert (Test-Path "$dir\GPL-3.0.txt") 'GPL text installed'
Assert (Test-Path "$dir\sources") 'corresponding sources installed'
Assert (Test-Path "$dir\unins000.exe") 'uninstaller installed'
Assert ((Version) -eq '0.0.1') 'old version registered'
Assert ($null -ne (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run').SymPortBridge) 'autostart task wrote the Run value'
& "$dir\SymPortBridge.exe" --self-test --report "$root\self-test-old.json"
Assert ($LASTEXITCODE -eq 0) 'installed exe passes its self-test'

# 2. User data that an update must keep.
New-Item -ItemType Directory -Force $data | Out-Null
Set-Content "$data\settings.json" '{"schema": 1, "auto_usb": true, "origins": [], "gammu_config": "", "volumes": {}}'
Set-Content "$data\keep-me.txt" 'private backup placeholder'

# 3. Update exactly as the Bridge launches it, while the old version is running.
$running = Start-Process "$dir\SymPortBridge.exe" -PassThru
Start-Sleep -Seconds 8
Assert (-not $running.HasExited) 'old Bridge is running'
Run $New @('/SILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/StartAfter=1', "/LOG=$root\new.log")
Assert ((Version) -eq $NewVersion) "upgraded to $NewVersion"
Assert (@(Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall' | Where-Object { $_.PSChildName -like '{8F3C2B7A*' }).Count -eq 1) 'one uninstall entry only'
Assert (Test-Path "$data\keep-me.txt") 'user data kept by the update'
Assert (Test-Path "$data\settings.json") 'settings kept by the update'
Assert ($running.HasExited) 'running old Bridge was closed by the update'
Start-Sleep -Seconds 10
$restarted = Get-Process SymPortBridge -ErrorAction SilentlyContinue
Assert ($null -ne $restarted) 'new Bridge was started after the silent update (/StartAfter=1)'
$restarted | Stop-Process -Force
Start-Sleep -Seconds 2
& "$dir\SymPortBridge.exe" --self-test --report "$root\self-test-new.json"
Assert ($LASTEXITCODE -eq 0) 'updated exe passes its self-test'

# 4. Uninstall: program gone, entry gone, data kept unless asked.
Run "$dir\unins000.exe" @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
Start-Sleep -Seconds 3
Assert (-not (Test-Path "$dir\SymPortBridge.exe")) 'exe removed'
Assert (-not (Test-Path $uninstallKey)) 'uninstall entry removed'
Assert ($null -eq (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue).SymPortBridge) 'autostart value removed'
Assert (Test-Path "$data\keep-me.txt") 'user data kept by a silent uninstall'

# 5. Reinstall + uninstall with /REMOVEDATA=1 removes the data directory.
Run $New @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=$dir")
Run "$dir\unins000.exe" @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/REMOVEDATA=1')
Start-Sleep -Seconds 3
Assert (-not (Test-Path $data)) 'data removed when requested'
Write-Host 'Installer: install, update over a running copy, data preservation, uninstall and data removal passed'
