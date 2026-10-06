param([switch]$CheckOnly, [switch]$InstallFigureTools)
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'Setup-Laptop.ps1') -CheckOnly:$CheckOnly -PatchManifest (Join-Path $PSScriptRoot 'laptop_patch_manifest.json')
if($InstallFigureTools) {
    & (Join-Path $PSScriptRoot '.venv-laptop\Scripts\python.exe') -m pip install -r (Join-Path $PSScriptRoot 'requirements-report.txt')
    if($LASTEXITCODE -ne 0) { throw 'Optional figure-tool installation failed.' }
}
Write-Host 'Start-Laptop.ps1 opens the guided workspace on localhost:8768. Figure downloads work without installing optional figure tools.'
