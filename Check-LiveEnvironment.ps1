$ErrorActionPreference='Stop'
$taskIdentity=[Security.Principal.WindowsIdentity]::GetCurrent()
$taskPrincipal=[Security.Principal.WindowsPrincipal]::new($taskIdentity)
$taskReport=[ordered]@{
    administrator=$taskPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    docker_command_available=[bool](Get-Command docker -ErrorAction SilentlyContinue)
    kubectl_command_available=[bool](Get-Command kubectl -ErrorAction SilentlyContinue)
    kind_command_available=[bool](Get-Command kind -ErrorAction SilentlyContinue)
    docker_engine_running=$false
    note='Read-only preflight; no installer or restart is invoked.'
}
if ($taskReport.docker_command_available) {
    & docker info --format '{{.ServerVersion}}'
    $taskReport.docker_engine_running=($LASTEXITCODE -eq 0)
}
$taskReport | ConvertTo-Json
$taskReport | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'artifacts\research\live_environment.json')
