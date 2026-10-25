[CmdletBinding()]
param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency step failed ($LASTEXITCODE): $Program $($Arguments -join ' '). Fix that prerequisite and rerun scripts/dev.ps1."
    }
}

Push-Location $repoRoot
try {
    foreach ($tool in @('python', 'node', 'pnpm', 'uv', 'cargo', 'rustc')) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            throw "Missing $tool. Install its version from toolchains.json, then rerun scripts/dev.ps1."
        }
    }
    Invoke-Checked 'python' @('scripts/check_workspace.py')
    Invoke-Checked 'python' @('scripts/check_toolchains.py', '--exact')
    if ($CheckOnly) { return }
    Invoke-Checked 'pnpm' @('install', '--frozen-lockfile')
    Invoke-Checked 'uv' @('sync', '--project', 'services/runtime', '--locked', '--python', (Get-Content .python-version -Raw).Trim())
    $env:VEYA_PYTHON = (Resolve-Path 'services/runtime/.venv/Scripts/python.exe').Path
    Invoke-Checked 'cargo' @('fetch', '--manifest-path', 'apps/desktop/src-tauri/Cargo.toml', '--locked')
    Invoke-Checked 'python' @('scripts/build_platform.py')
    Invoke-Checked 'pnpm' @('build')
    Write-Host 'VEYA_PYTHON now points to the locked runtime for this terminal.'
    Write-Host 'Veya is ready. Run pnpm web for the local workspace, or pnpm desktop:dev for the desktop app.'
} finally {
    Pop-Location
}
