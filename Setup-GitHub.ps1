param([switch]$CheckOnly)
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$runtime=Join-Path $projectRoot '.venv-laptop\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $runtime)) {
    if($CheckOnly) { throw 'Run Setup-GitHub.ps1 first.' }
    & py -3.14 -m venv (Join-Path $projectRoot '.venv-laptop')
    if($LASTEXITCODE -ne 0) { throw 'Official Python 3.14 with the py launcher is required.' }
}
Push-Location -LiteralPath $projectRoot
try {
    if(-not $CheckOnly) {
        & $runtime -m pip install -r requirements-laptop.txt
        if($LASTEXITCODE -ne 0) { throw 'CPU dependency installation failed.' }
    }
    & $runtime -m scripts.verify_repository
    if($LASTEXITCODE -ne 0) { throw 'Publication verification failed.' }
} finally { Pop-Location }
Write-Host 'CPU repository checked. Start-Laptop.ps1 starts the dashboard without training.'
