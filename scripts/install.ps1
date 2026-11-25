$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (Get-Command py -ErrorAction SilentlyContinue) {
    $py = "py"
    $args = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $py = "python"
    $args = @()
} else {
    throw "Install Python 3.11 or newer."
}
& $py @args -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'"
if (-not (Test-Path .venv)) { & $py @args -m venv .venv }
$p = ".\.venv\Scripts\python.exe"
& $p -m pip install --upgrade pip
& $p -m pip install -r requirements.txt
& $p -m pip check
Write-Host "NEXUS AI installation complete."
Write-Host "Start dashboard: .\.venv\Scripts\python.exe -m uvicorn dashboard.app:app --host 127.0.0.1 --port 8000"
