param(
    [ValidateSet('frontend','checkout','inventory')][string]$Target='inventory',
    [ValidateSet('delay','error','unavailable')][string]$Fault='delay',
    [ValidateRange(5,120)][int]$DurationSeconds=30,
    [string]$Context='kind-incidentlab'
)
$ErrorActionPreference='Stop'
if($Context -ne 'kind-incidentlab') { throw 'This staging runner only supports the dedicated kind-incidentlab test context.' }
if(-not (Get-Command kubectl -ErrorAction SilentlyContinue)) { throw 'kubectl is required; no cluster operation performed.' }
$namespaceName='incidentlab-testbed'
$deploymentName="deployment/$Target"
function Invoke-TestbedKubectl([string[]]$Arguments) {
    $output = & kubectl --context $Context -n $namespaceName @Arguments
    if($LASTEXITCODE -ne 0) { throw "kubectl failed: $Arguments" }
    return $output
}
$metadata = (Invoke-TestbedKubectl @('get',$deploymentName,'-o','json')) | ConvertFrom-Json
if($metadata.metadata.labels.'app.kubernetes.io/part-of' -ne 'incidentlab-testbed') {
    throw 'Target does not belong to the isolated testbed.'
}
$projectRoot=Split-Path -Parent $PSScriptRoot
$archivePath=Join-Path $projectRoot 'artifacts\kubernetes'
New-Item -ItemType Directory -Force -Path $archivePath | Out-Null
$runName=Get-Date -Format 'yyyyMMddTHHmmss'
$schedulePath=Join-Path $archivePath "$runName-$Target-$Fault.json"
$schedule=[ordered]@{context=$Context;namespace=$namespaceName;target=$Target;fault=$Fault;requestedDurationSeconds=$DurationSeconds;status='starting'}
try {
    Invoke-TestbedKubectl @('rollout','status',$deploymentName,'--timeout=120s') | Out-Host
    if($Fault -eq 'unavailable') {
        Invoke-TestbedKubectl @('scale',$deploymentName,'--replicas=0') | Out-Host
    } else {
        $scriptText="import json,pathlib; p=pathlib.Path('/telemetry/control.json'); t=p.with_suffix('.tmp'); t.write_text(json.dumps({'$Target':'$Fault'})); t.replace(p)"
        Invoke-TestbedKubectl @('exec',$deploymentName,'--','python','-c',$scriptText) | Out-Host
    }
    $schedule.commandCompletedUtc=[DateTime]::UtcNow.ToString('o')
    $schedule.status='active'
    $schedule | ConvertTo-Json | Set-Content -LiteralPath $schedulePath -Encoding utf8
    Start-Sleep -Seconds $DurationSeconds
} finally {
    if($Fault -eq 'unavailable') {
        Invoke-TestbedKubectl @('scale',$deploymentName,'--replicas=1') | Out-Host
        Invoke-TestbedKubectl @('rollout','status',$deploymentName,'--timeout=120s') | Out-Host
    } else {
        $resetScript="import pathlib; p=pathlib.Path('/telemetry/control.json'); t=p.with_suffix('.tmp'); t.write_text('{}'); t.replace(p)"
        Invoke-TestbedKubectl @('exec',$deploymentName,'--','python','-c',$resetScript) | Out-Host
    }
    $schedule.recoveryCommandCompletedUtc=[DateTime]::UtcNow.ToString('o')
    $schedule.status='recovered'
    $schedule | ConvertTo-Json | Set-Content -LiteralPath $schedulePath -Encoding utf8
    Write-Host "Archived control commands: $schedulePath. Confirm actual workload impact/onset separately."
}
