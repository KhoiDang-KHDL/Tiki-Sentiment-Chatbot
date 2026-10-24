param(
    [ValidateSet('setup','start','stop','status','check','logs','build','test')]
    [string]$Action = 'status'
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $projectRoot
function Invoke-Stack {
    $composeArgs = @('compose','--env-file','.env.airflow','--env-file','.env.docker')
    if (Test-Path -LiteralPath .env.monitoring) { $composeArgs += @('--env-file','.env.monitoring') }
    & docker @composeArgs --file docker-compose.yml @args
    if ($LASTEXITCODE -ne 0) { throw "Compose command failed (exit $LASTEXITCODE)." }
}
if ($Action -eq 'setup') {
    # Reuse/create Airflow and the existing Qdrant network without removing volumes.
    & .\scripts\airflow.ps1 setup
    if ($LASTEXITCODE -ne 0) { throw 'Airflow setup failed.' }
    if (Test-Path -LiteralPath .\set_env.ps1) { . .\set_env.ps1 | Out-Null }
    & .\.venv\Scripts\python.exe -m scripts.docker_config
    if ($LASTEXITCODE -ne 0) { throw 'Docker configuration generation failed.' }
    & .\scripts\monitoring.ps1 config
    [IO.Directory]::CreateDirectory((Join-Path $projectRoot 'logs')) | Out-Null
    Invoke-Stack config --quiet
    Invoke-Stack build api ui
    Invoke-Stack up -d --wait --wait-timeout 600
    Invoke-Stack ps
    exit 0
}
foreach ($file in @('.env.airflow','.env.docker')) {
    if (-not (Test-Path -LiteralPath $file)) { throw 'Run scripts/stack.ps1 setup first.' }
}
switch ($Action) {
    'start' {
        & .\scripts\airflow.ps1 start
        Invoke-Stack up -d --wait --wait-timeout 600
    }
    'stop' { Invoke-Stack stop }
    'status' { Invoke-Stack ps }
    'build' { Invoke-Stack build api ui }
    'logs' { Invoke-Stack logs --tail 100 api ui }
    'check' {
        Invoke-Stack exec -T ui python -m source.chatbot.container_check
        if (Test-Path -LiteralPath .env.monitoring) { Invoke-Stack exec -T ui python -m source.chatbot.monitoring_check }
    }
    'test' {
        & .\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
        if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
        & .\scripts\airflow.ps1 test
    }
}
