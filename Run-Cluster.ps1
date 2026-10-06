param([ValidateSet('Check','Deploy','Quick','Validate')][string]$Mode='Check')
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$pythonRuntime=Join-Path $projectRoot '.venv-laptop\Scripts\python.exe'
foreach($commandName in @('docker','kind','kubectl')) {
    if(-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "$commandName is missing. Install the laptop prerequisites described in TRANSFER_README.md."
    }
}
function Invoke-Checked([string]$Program,[string[]]$Arguments) {
    & $Program @Arguments
    if($LASTEXITCODE -ne 0) { throw "$Program failed; inspect the output above." }
}
Push-Location $projectRoot
try {
    Invoke-Checked docker @('version')
    $engineOS = & docker info --format '{{.OSType}}'
    if($LASTEXITCODE -ne 0 -or $engineOS -ne 'linux') { throw 'Start Docker Desktop using Linux containers on your laptop first.' }
    Invoke-Checked kind @('version')
    Invoke-Checked kubectl @('version','--client=true')
    $driveInfo=Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($projectRoot).Substring(0,1))
    Write-Host ('Free disk: {0:N1} GB. Docker images need additional disk space.' -f ($driveInfo.Free/1GB))
    if($Mode -eq 'Check') { return }
    if(-not (Test-Path -LiteralPath $pythonRuntime)) { throw 'Run .\Setup-Laptop.ps1 first.' }
    if($Mode -eq 'Deploy') {
        $clusters = & kind get clusters
        if($LASTEXITCODE -ne 0) { throw 'Unable to inspect kind clusters.' }
        if($clusters -notcontains 'incidentlab') {
            Invoke-Checked kind @('create','cluster','--name','incidentlab','--config','deployment/kind-laptop.yaml','--wait','120s')
        }
        # Limit only this named kind node; verify its ownership before changing its resources.
        $nodeJson = & docker inspect incidentlab-control-plane
        if($LASTEXITCODE -ne 0) { throw 'Unable to inspect the named node.' }
        $nodeObjects = @($nodeJson | ConvertFrom-Json)
        if($nodeObjects.Count -ne 1 -or $nodeObjects[0].Config.Labels.'io.x-k8s.kind.cluster' -ne 'incidentlab') { throw 'Named node is not owned by the IncidentLab kind cluster.' }
        Invoke-Checked docker @('update','--cpus','2','--memory','4g','--memory-swap','4g','incidentlab-control-plane')
        $namespace = & kubectl --context kind-incidentlab get namespace incidentlab-testbed --ignore-not-found=true -o json
        if($LASTEXITCODE -ne 0) { throw 'Unable to inspect target namespace.' }
        if($namespace) {
            $namespaceObject=$namespace | ConvertFrom-Json
            if($namespaceObject.metadata.labels.'app.kubernetes.io/part-of' -ne 'incidentlab-testbed') { throw 'Existing namespace has different ownership.' }
            foreach($serviceName in @('frontend','checkout','inventory')) {
                $existing = & kubectl --context kind-incidentlab -n incidentlab-testbed get "deployment/$serviceName" --ignore-not-found=true -o json
                if($LASTEXITCODE -ne 0) { throw 'Unable to inspect deployment ownership.' }
                if($existing -and (($existing | ConvertFrom-Json).metadata.labels.'app.kubernetes.io/part-of' -ne 'incidentlab-testbed')) { throw 'Existing deployment has different ownership.' }
            }
        }
        Invoke-Checked docker @('build','-f','deployment/Dockerfile.testbed','-t','incidentlab-testbed:dev','.')
        Invoke-Checked kind @('load','docker-image','incidentlab-testbed:dev','--name','incidentlab')
        Invoke-Checked kubectl @('--context','kind-incidentlab','apply','-f','deployment/kubernetes-testbed.yaml')
        foreach($serviceName in @('frontend','checkout','inventory')) {
            Invoke-Checked kubectl @('--context','kind-incidentlab','-n','incidentlab-testbed','rollout','status',"deployment/$serviceName",'--timeout=120s')
        }
        Write-Host 'Testbed deployed. Next run .\Run-Cluster.ps1 -Mode Quick'
    } else {
        $experimentArguments=@('-m','incidentlab.kubernetes_experiment')
        if($Mode -eq 'Quick') { $experimentArguments += '--quick' }
        Invoke-Checked $pythonRuntime $experimentArguments
    }
} finally { Pop-Location }
