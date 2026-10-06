# Only the owned local experiment uses short termination for bounded scale-down faults.
$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    $namespace = & kubectl --context kind-incidentlab get namespace incidentlab-testbed -o json
    if($LASTEXITCODE -ne 0 -or ($namespace | ConvertFrom-Json).metadata.labels.'app.kubernetes.io/part-of' -ne 'incidentlab-testbed') { throw 'Namespace ownership check failed.' }
    foreach($service in @('frontend','checkout','inventory')) {
        $raw = & kubectl --context kind-incidentlab -n incidentlab-testbed get "deployment/$service" -o json
        if($LASTEXITCODE -ne 0) { throw 'Deployment inspection failed.' }
        $deployment=$raw | ConvertFrom-Json
        if($deployment.metadata.labels.'app.kubernetes.io/part-of' -ne 'incidentlab-testbed' -or $deployment.spec.replicas -ne 1) { throw 'Expected an owned deployment with one healthy replica.' }
    }
    foreach($service in @('frontend','checkout','inventory')) {
        & kubectl --context kind-incidentlab -n incidentlab-testbed patch "deployment/$service" --type=merge --patch-file deployment/laptop-termination.patch.json
        if($LASTEXITCODE -ne 0) { throw 'Termination configuration failed.' }
        & kubectl --context kind-incidentlab -n incidentlab-testbed rollout status "deployment/$service" --timeout=120s
        if($LASTEXITCODE -ne 0) { throw 'Rollout failed.' }
    }
    Write-Host 'Owned local testbed uses one-second pod termination; not a production setting.'
} finally { Pop-Location }
