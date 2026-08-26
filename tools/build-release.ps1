param([Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
  .\.venv\Scripts\python.exe -m pip install '.[build]'
  .\.venv\Scripts\python.exe -m unittest discover -s application/tests
  .\.venv\Scripts\pyinstaller.exe --noconfirm --clean tools\serial-vision.spec
  & iscc.exe "/DAppVersion=$Version" installer\serial-vision.iss
  if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed: $LASTEXITCODE" }
} finally { Pop-Location }
