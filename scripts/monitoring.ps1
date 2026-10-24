param(
    [ValidateSet('config','setup','start','status','password','check','locust')]
    [string]$Action = 'status'
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $projectRoot
$envPath = Join-Path $projectRoot '.env.monitoring'
if ($Action -in @('config','setup')) {
    if (-not (Test-Path -LiteralPath $envPath)) {
        $bytes = New-Object byte[] 32
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        $password = [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()
        $template = [IO.File]::ReadAllText((Join-Path $projectRoot '.env.monitoring.example'))
        $template = $template.Replace('GENERATE_WITH_SETUP', $password)
        [IO.File]::WriteAllText($envPath, $template, (New-Object Text.UTF8Encoding $false))
        Write-Host 'Created private Grafana credentials in .env.monitoring (not printed).'
    }
    [IO.Directory]::CreateDirectory((Join-Path $projectRoot 'reports/loadtest')) | Out-Null
    if ($Action -eq 'config') { return }
}
if (-not (Test-Path -LiteralPath $envPath)) { throw 'Run scripts/monitoring.ps1 setup first.' }
function Invoke-Monitoring {
    & docker compose --env-file .env.airflow --env-file .env.docker --env-file .env.monitoring --file docker-compose.yml @args
    if ($LASTEXITCODE -ne 0) { throw "Monitoring command failed (exit $LASTEXITCODE)." }
}
switch ($Action) {
    'setup' {
        Invoke-Monitoring config --quiet
        Invoke-Monitoring pull prometheus grafana locust
        Invoke-Monitoring build api ui
        Invoke-Monitoring up -d --wait --wait-timeout 600 api ui prometheus grafana
    }
    'start' { Invoke-Monitoring up -d --wait --wait-timeout 600 prometheus grafana }
    'status' { Invoke-Monitoring ps }
    'password' {
        $line = [IO.File]::ReadAllLines($envPath) | Where-Object { $_ -match '^GRAFANA_ADMIN_PASSWORD=' }
        Write-Host 'Grafana username: admin'
        Write-Host ('Grafana password: ' + ($line -split '=',2)[1])
    }
    'locust' { Invoke-Monitoring --profile loadtest up -d --wait --wait-timeout 180 api-loadtest locust }
    'check' { Invoke-Monitoring exec -T ui python -m source.chatbot.monitoring_check }
}
