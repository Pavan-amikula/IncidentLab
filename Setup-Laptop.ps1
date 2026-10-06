param([switch]$CheckOnly, [string]$PatchManifest)
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$laptopPython=Join-Path $projectRoot '.venv-laptop\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $laptopPython)) {
    if($CheckOnly) { throw 'Run Setup-Laptop.ps1 to create the CPU environment first.' }
    if(-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install official 64-bit Python 3.14 with its py launcher, then rerun this script.' }
    & py -3.14 -m venv (Join-Path $projectRoot '.venv-laptop')
    if($LASTEXITCODE -ne 0) { throw 'Python 3.14 is required for the recorded artifact/dependency versions.' }
}
if(-not $CheckOnly) {
    & $laptopPython -m pip install -r (Join-Path $projectRoot 'requirements-laptop.txt')
    if($LASTEXITCODE -ne 0) { throw 'CPU dependency installation failed.' }
}
Push-Location -LiteralPath $projectRoot
try {
    $verifyArguments=@('-m','scripts.verify_laptop','--require-manifest')
    if($PatchManifest) { $verifyArguments += @('--patch-manifest',$PatchManifest) }
    & $laptopPython @verifyArguments
    if($LASTEXITCODE -ne 0) { throw 'Laptop artifact or CPU smoke verification failed.' }
} finally { Pop-Location }
Write-Host 'CPU handoff checked. Start-Laptop.ps1 starts the dashboard; it does not retrain.' -ForegroundColor Green
