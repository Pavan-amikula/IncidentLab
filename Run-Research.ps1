param([ValidateSet('Inspect','Temporal','All')][string]$Mode='Inspect')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$logDirectory=Join-Path $PSScriptRoot 'artifacts\logs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Start-Transcript -Path (Join-Path $logDirectory 'latest-research-run.log') -Force
function Invoke-ResearchStage([string[]]$stageArguments) {
    Write-Host ('RUN: .venv\Scripts\python.exe '+($stageArguments -join ' '))
    & $taskPython @stageArguments
    if ($LASTEXITCODE -ne 0) {throw 'Research stage failed; later stages stopped.'}
}
try {
    if ($Mode -eq 'All') {
        foreach ($stage in @('prepare','train','validate','test')) {
            Invoke-ResearchStage -stageArguments @('-m','incidentlab.research_pipeline',$stage)
        }
    }
    if ($Mode -in @('Temporal','All')) {
        Invoke-ResearchStage -stageArguments @('-m','incidentlab.trace_features')
        Invoke-ResearchStage -stageArguments @('-m','incidentlab.temporal_model','train','--epochs','12')
        Invoke-ResearchStage -stageArguments @('-m','incidentlab.temporal_model','evaluate')
        Invoke-ResearchStage -stageArguments @('-m','incidentlab.supervised_reference')
    }
    Invoke-ResearchStage -stageArguments @('scripts\summarize_experiments.py')
} finally {Stop-Transcript}
