param([Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
  uv sync --locked --extra build
  if ($LASTEXITCODE -ne 0) { throw "Dependency sync failed" }
  uv run --locked --extra build ruff check .
  if ($LASTEXITCODE -ne 0) { throw "Ruff lint failed" }
  uv run --locked --extra build ruff format --check .
  if ($LASTEXITCODE -ne 0) { throw "Ruff formatting failed" }
  uv run --locked --extra build mypy
  if ($LASTEXITCODE -ne 0) { throw "Type checks failed" }
  uv run --locked --extra build python -m unittest discover -s application/tests
  if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
  uv run --locked --extra build python -m PyInstaller --noconfirm --clean tools\serial-vision.spec
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
  & iscc.exe "/DAppVersion=$Version" installer\serial-vision.iss
  if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed: $LASTEXITCODE" }
} finally { Pop-Location }
