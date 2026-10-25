$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
  uv run --locked serial-vision
  if ($LASTEXITCODE -ne 0) { throw "Serial Vision failed: $LASTEXITCODE" }
} finally { Pop-Location }
