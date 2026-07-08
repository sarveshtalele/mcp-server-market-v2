# Runs agentgateway in front of the MCP server (governance allowlist + audit
# log; see config.yaml). Run setup.ps1 first if bin/agentgateway.exe is missing.
$ErrorActionPreference = "Stop"
$exe = Join-Path $PSScriptRoot "bin\agentgateway.exe"
$cfg = Join-Path $PSScriptRoot "config.yaml"

if (-not (Test-Path $exe)) {
    Write-Host "agentgateway.exe not found — run setup.ps1 first."
    exit 1
}

& $exe -f $cfg
