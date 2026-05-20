$ErrorActionPreference = "Stop"

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment not found at venv\Scripts\python.exe"
}

& $venvPython -m pip install -r requirements.txt
& $venvPython -m PyInstaller --noconfirm --clean VendorQuoteComparisonTool.spec

Write-Host ""
Write-Host "Build complete."
Write-Host "Executable: dist\VendorQuoteComparisonTool.exe"
