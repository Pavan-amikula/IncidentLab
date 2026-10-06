param([int]$Port = 8767)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Create .venv and install requirements.txt first; see README.md.' }
    $taskModel = Join-Path $PSScriptRoot 'artifacts\models\detector.joblib'
    if (-not (Test-Path -LiteralPath $taskModel)) { throw 'Run the prepare, train, and validate stages first; see README.md.' }
    & $taskPython -m uvicorn incidentlab.server:app --host 127.0.0.1 --port $Port
} finally { Pop-Location }
