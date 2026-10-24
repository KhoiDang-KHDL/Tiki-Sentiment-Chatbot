param([switch]$Install)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $root
$ciPython = Join-Path $root '.venv-ci/Scripts/python.exe'
if ($Install) {
    if (-not (Test-Path -LiteralPath $ciPython)) {
        & py -3.12 -m venv .venv-ci
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 with the Windows Python launcher, then retry.' }
    }
    & $ciPython -m pip install -r requirements-ci.txt
    if ($LASTEXITCODE -ne 0) { throw 'CI dependency installation failed.' }
}
if (-not (Test-Path -LiteralPath $ciPython)) { throw 'First run: scripts/ci.ps1 -Install (requires Python 3.12).' }
& $ciPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'CI dependency conflicts.' }
& $ciPython -m scripts.ci_checks
if ($LASTEXITCODE -ne 0) { throw 'CI static checks failed.' }
& $ciPython -X utf8 -m scripts.ci_tests
if ($LASTEXITCODE -ne 0) { throw 'CI regression tests failed. Read reports/ci/unit-tests.txt.' }
