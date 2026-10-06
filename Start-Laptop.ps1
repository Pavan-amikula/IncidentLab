param([ValidateRange(1024,65535)][int]$Port=8768)
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$laptopPython=Join-Path $projectRoot '.venv-laptop\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $laptopPython)) { throw 'Run Setup-Laptop.ps1 first.' }
$env:INCIDENTLAB_DISABLE_LLM='1'
$env:OMP_NUM_THREADS='2'
$env:MKL_NUM_THREADS='2'
$env:CUDA_VISIBLE_DEVICES='-1'
Push-Location -LiteralPath $projectRoot
try {
    Write-Host "CPU dashboard: http://127.0.0.1:$Port . Training and local LLM generation are disabled in this launch."
    & $laptopPython -m uvicorn incidentlab.research_server:app --host 127.0.0.1 --port $Port --workers 1
    if($LASTEXITCODE -ne 0) { throw 'Dashboard stopped with an error.' }
} finally { Pop-Location }
