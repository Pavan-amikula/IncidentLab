param([switch]$AllowLegacyCgroupV1)
$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    & powershell -ExecutionPolicy Bypass -File .\Run-Cluster.ps1 -Mode Check
    if($LASTEXITCODE -ne 0) { throw 'Cluster prerequisite Check failed.' }
    $clusters = & kind get clusters
    if($LASTEXITCODE -ne 0) { throw 'Unable to inspect kind clusters.' }
    if($clusters -contains 'incidentlab') { throw 'The named cluster already exists. Inspect it and use Run-Cluster.ps1 -Mode Deploy; this script only creates a new cluster.' }
    $cgroupVersion = & docker info --format '{{.CgroupVersion}}'
    if($LASTEXITCODE -ne 0) { throw 'Unable to inspect Docker cgroup version.' }
    $nodeConfig='deployment/kind-laptop.yaml'
    if($cgroupVersion -eq '1') {
        if(-not $AllowLegacyCgroupV1) { throw 'Docker uses deprecated cgroup v1. Migrate to cgroup v2 or explicitly use -AllowLegacyCgroupV1 for this isolated research testbed.' }
        $nodeConfig='deployment/kind-laptop-cgroupv1.yaml'
        Write-Warning 'Explicit cgroup-v1 compatibility is temporary research configuration, not a production default.'
    }
    & kind create cluster --name incidentlab --config $nodeConfig --wait 120s
    if($LASTEXITCODE -ne 0) { throw 'Cluster creation failed. Inspect the output; no application fault has been injected.' }
    Write-Host 'Cluster created. Continue with Run-Cluster.ps1 -Mode Deploy.'
} finally { Pop-Location }
