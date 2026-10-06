param(
    [ValidateSet('Collect','Validation','Runtime','Semantic','OpenStack','Parameters','LLM','Inspect')]
    [string]$Mode = 'Collect',
    [int]$Seconds = 120,
    [ValidateRange(1,60)][int]$Minutes=10,
    [ValidateSet('v1','v2')][string]$PolicyVersion='v1'
)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonRuntime = Join-Path $projectRoot '.venv\Scripts\python.exe'
Push-Location -LiteralPath $projectRoot
try {
    Write-Host "IncidentLab: $Mode" -ForegroundColor Cyan
    switch ($Mode) {
        'Collect' {
            Write-Host 'Real HTTP services; separate training/calibration, two controls and nine fault trials across three targets.'
            Write-Host "Command: python -u -m incidentlab.native_experiment --seconds $Seconds --window 3 --healthy-loads --fault-targets frontend checkout inventory"
            & $pythonRuntime -u -m incidentlab.native_experiment --seconds $Seconds --window 3 --healthy-loads --fault-targets frontend checkout inventory
        }
        'Semantic' { & $pythonRuntime -u -m incidentlab.semantic_log_content }
        'Runtime' {
            $completedReport = Get-Content -LiteralPath (Join-Path $projectRoot 'artifacts\live\latest_report.json') -Raw | ConvertFrom-Json
            $selectedRun = $completedReport.run_id
            Write-Host "Command: python -u -m incidentlab.native_runtime --run-id $selectedRun --minutes $Minutes"
            & $pythonRuntime -u -m incidentlab.native_runtime --run-id $selectedRun --minutes $Minutes
        }
        'Validation' {
            Write-Host 'Fresh healthy training/calibration, twenty minutes of controls, twice each three-service fault. Approximately 57 minutes.'
            Write-Host 'Command: python -u -m incidentlab.native_experiment --seconds 90 --healthy-seconds 300 --control-seconds 600 --repetitions 2 --window 3 --healthy-loads --fault-targets frontend checkout inventory'
            & $pythonRuntime -u -m incidentlab.native_experiment --seconds 90 --healthy-seconds 300 --control-seconds 600 --repetitions 2 --window 3 --healthy-loads --fault-targets frontend checkout inventory
        }
        'OpenStack' { & $pythonRuntime -u -m incidentlab.openstack_benchmark }
        'Parameters' { & $pythonRuntime -u -m incidentlab.openstack_parameters }
        'LLM' { & $pythonRuntime -u -m incidentlab.llm_live_evaluation --policy-version $PolicyVersion }
        'Inspect' { Get-Content -LiteralPath (Join-Path $projectRoot 'artifacts\live\latest_report.json') }
    }
    if ($LASTEXITCODE -ne 0 -and $Mode -ne 'Inspect') { throw "Stage failed with exit code $LASTEXITCODE" }
} finally { Pop-Location }
