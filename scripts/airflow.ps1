param(
    [ValidateSet('setup','start','stop','status','check','test','logs','password')]
    [string]$Action = 'status',
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$envPath = Join-Path $projectRoot '.env.airflow'
$composePath = Join-Path $projectRoot 'docker-compose.airflow.yml'
Set-Location -LiteralPath $projectRoot

function New-LocalToken {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()
}

function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE)." }
}

function Invoke-Compose {
    & docker compose --env-file $envPath --file $composePath @args
    if ($LASTEXITCODE -ne 0) { throw "Compose command failed (exit $LASTEXITCODE)." }
}

function Read-Settings {
    $values = @{}
    foreach ($line in [IO.File]::ReadAllLines($envPath)) {
        if ($line -match '^([A-Z0-9_]+)=(.*)$') { $values[$Matches[1]] = $Matches[2] }
    }
    return $values
}

if ($Action -eq 'setup') {
    if (-not (Test-Path -LiteralPath $envPath)) {
        $template = [IO.File]::ReadAllText((Join-Path $projectRoot '.env.airflow.example'))
        foreach ($key in @('AIRFLOW_POSTGRES_PASSWORD','AIRFLOW_JWT_SECRET','AIRFLOW_API_SECRET','AIRFLOW_ADMIN_PASSWORD')) {
            $template = $template.Replace("$key=GENERATE_WITH_SETUP", "$key=$(New-LocalToken)")
        }
        $hubCache = (Join-Path $env:USERPROFILE '.cache\huggingface\hub').Replace('\','/')
        $template = $template.Replace('C:/Users/User/.cache/huggingface/hub', $hubCache)
        [IO.File]::WriteAllText($envPath, $template, (New-Object Text.UTF8Encoding $false))
        Write-Host 'Created .env.airflow with local credentials (not printed).'
    }
    foreach ($relative in @('airflow/logs','data/airflow_queue/inbox','data/airflow_queue/processing',
                            'data/airflow_queue/archive','data/airflow_queue/receipts','data/airflow_queue/results')) {
        [IO.Directory]::CreateDirectory((Join-Path $projectRoot $relative)) | Out-Null
    }
}

if (-not (Test-Path -LiteralPath $envPath)) {
    throw 'Run: .\scripts\airflow.ps1 setup'
}
$settings = Read-Settings
if ($Action -eq 'password') {
    Write-Host 'Username: admin'
    Write-Host "Password: $($settings['AIRFLOW_ADMIN_PASSWORD'])"
    exit 0
}
Invoke-Docker info --format '{{.ServerVersion}}'

if ($Action -in @('setup','start')) {
    if (-not (Test-Path -LiteralPath $settings['HF_HUB_CACHE_HOST'])) {
        [IO.Directory]::CreateDirectory($settings['HF_HUB_CACHE_HOST']) | Out-Null
    }
    $containerName = $settings['QDRANT_CONTAINER']
    $networkName = $settings['AIRFLOW_NETWORK']
    $containerJson = & docker inspect $containerName
    if ($LASTEXITCODE -ne 0) { throw "Existing Qdrant container '$containerName' not found. Update .env.airflow." }
    $containerInfo = ($containerJson | ConvertFrom-Json)[0]
    $networkNames = @(& docker network ls --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot list Docker networks.' }
    if ($networkName -notin $networkNames) { Invoke-Docker network create $networkName }
    if ($networkName -notin @($containerInfo.NetworkSettings.Networks.PSObject.Properties.Name)) {
        Invoke-Docker network connect --alias qdrant $networkName $containerName
    }
    if (-not $containerInfo.State.Running) { Invoke-Docker start $containerName }
}

switch ($Action) {
    'setup' {
        Invoke-Compose config --quiet
        if (-not $SkipBuild) { Invoke-Compose build airflow-scheduler }
        Invoke-Compose run --rm --no-deps airflow-permissions
        Invoke-Compose run --rm airflow-init
        Invoke-Compose up -d --wait --wait-timeout 240 postgres airflow-api-server airflow-scheduler airflow-dag-processor
        Write-Host "Airflow ready: http://localhost:$($settings['AIRFLOW_UI_PORT'])"
        Write-Host 'DAG is paused. Run scripts/airflow.ps1 password to see local login.'
    }
    'start' {
        Invoke-Compose up -d --wait --wait-timeout 240 postgres airflow-api-server airflow-scheduler airflow-dag-processor
    }
    'stop' { Invoke-Compose stop }
    'status' { Invoke-Compose ps }
    'logs' { Invoke-Compose logs --tail 100 airflow-api-server airflow-scheduler airflow-dag-processor }
    'check' {
        Invoke-Compose exec -T airflow-scheduler /opt/tiki-venv/bin/python -m scripts.airflow_check
        Invoke-Compose exec -T airflow-dag-processor airflow dags list-import-errors
    }
    'test' {
        Invoke-Compose exec -T airflow-dag-processor python -m unittest discover -s tests -p test_airflow_dags.py -v
        Invoke-Compose exec -T airflow-scheduler /opt/tiki-venv/bin/python -m unittest discover -s tests -p test_kb_incremental.py -v
    }
}
