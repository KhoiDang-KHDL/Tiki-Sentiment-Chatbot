param(
    [ValidateSet('health','search','chat','stream','mixed')][string]$Scenario = 'mixed',
    [ValidateSet('synthetic','real')][string]$Target = 'synthetic',
    [ValidateRange(1,100)][int]$Users = 5,
    [ValidateRange(10,600)][int]$Seconds = 30,
    [ValidateRange(1,10)][int]$SpawnRate = 1,
    [ValidateRange(100,180000)][int]$P95Milliseconds = 10000,
    [ValidateRange(0,20)][int]$WarmupRequests = 0,
    [switch]$AllowLiveLlm
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $root
if ($Target -eq 'real' -and $Scenario -in @('chat','stream','mixed') -and -not $AllowLiveLlm) {
    throw 'Real chat sends retrieved data to the configured provider and uses quota. Use synthetic, or explicitly pass -AllowLiveLlm when authorized.'
}
function Invoke-LoadCompose {
    & docker compose --env-file .env.airflow --env-file .env.docker --env-file .env.monitoring --file docker-compose.yml @args
    if ($LASTEXITCODE -ne 0) { throw "Load-test command failed (exit $LASTEXITCODE). Inspect reports/loadtest." }
}
if (-not (Test-Path -LiteralPath .env.monitoring)) { throw 'Run scripts/monitoring.ps1 setup first.' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$runName = "$stamp-$Target-$Scenario-u$Users"
[IO.Directory]::CreateDirectory((Join-Path $root "reports/loadtest/$runName")) | Out-Null
$reportRoot = "/reports/$runName"
$classes = @{health='HealthUser'; search='SearchUser'; chat='ChatUser'; stream='StreamingUser'; mixed='MixedUser'}
$className = $classes[$Scenario]
$targetUrl = if ($Target -eq 'synthetic') { 'http://api-loadtest:8000' } else { 'http://api:8000' }
Invoke-LoadCompose --profile loadtest up -d --wait --wait-timeout 180 api-loadtest
if ($WarmupRequests -gt 0) {
    Invoke-LoadCompose --profile loadtest run --rm -T --no-deps --entrypoint python locust `
        /mnt/locust/loadtest_warmup.py --host $targetUrl --requests $WarmupRequests --output "$reportRoot/warmup.json"
}
$allow = if ($AllowLiveLlm) { '1' } else { '0' }
Invoke-LoadCompose --profile loadtest run --rm -T `
    -e "ALLOW_LIVE_LLM=$allow" -e "LOADTEST_MODE=$Target" -e "LOADTEST_SCENARIO=$Scenario" `
    -e "LOADTEST_P95_MS=$P95Milliseconds" -e "LOADTEST_SUMMARY=$reportRoot/summary.json" `
    -e "LOADTEST_WARMUP_REQUESTS=$WarmupRequests" `
    locust -f /mnt/locust/load_test.py --headless --host $targetUrl `
    --users $Users --spawn-rate $SpawnRate --run-time "$($Seconds)s" --stop-timeout 190 `
    --only-summary --html "$reportRoot/report.html" $className
Write-Host "Reports: reports/loadtest/$runName"
