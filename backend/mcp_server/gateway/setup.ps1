# Downloads agentgateway-windows-amd64.exe into backend/mcp_server/gateway/bin/.
# Run once per machine (the binary itself is gitignored, not committed).
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$version = "v1.3.1"
$url = "https://github.com/agentgateway/agentgateway/releases/download/$version/agentgateway-windows-amd64.exe"
$binDir = Join-Path $PSScriptRoot "bin"
$out = Join-Path $binDir "agentgateway.exe"

New-Item -ItemType Directory -Force -Path $binDir | Out-Null
Write-Host "Downloading agentgateway $version..."
Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
Write-Host "Installed: $out"
& $out --version
