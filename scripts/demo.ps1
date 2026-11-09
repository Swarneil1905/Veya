[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Model,
    [ValidateRange(1024, 131072)][int]$Context = 8192,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    python scripts/check_toolchains.py --bootstrap
    if ($LASTEXITCODE -ne 0) { throw 'Install the pinned Python and Node prerequisites.' }
    uv sync --project services/runtime --locked
    if ($LASTEXITCODE -ne 0) { throw 'Runtime dependency installation failed.' }
    $demoArgs = @('--model', $Model, '--context', $Context)
    if ($CheckOnly) { $demoArgs += '--check-only' }
    uv run --project services/runtime --locked python -m scripts.demo @demoArgs
    if ($LASTEXITCODE -ne 0) { throw 'Demo did not pass. Inspect the retained diagnostic output.' }
} finally {
    Pop-Location
}
