param(
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "NEXUS-AI Windows Installer" -ForegroundColor Cyan

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher not found. Install Python $PythonVersion from python.org and enable the Python Launcher."
}

& py "-$PythonVersion" --version
if ($LASTEXITCODE -ne 0) {
    throw "Python $PythonVersion is unavailable. Install it or specify another supported version."
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    & py "-$PythonVersion" -m venv (Join-Path $Root ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the virtual environment."
    }
}

& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }

& $Python -m pip install -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

& $Python -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency validation failed." }

& $Python -c "import core.cli; import dashboard.app; print('NEXUS-AI imports: OK')"
if ($LASTEXITCODE -ne 0) { throw "Application import validation failed." }

Write-Host ""
Write-Host "Installation completed successfully." -ForegroundColor Green
Write-Host "Start NEXUS-AI with:"
Write-Host "  .\.venv\Scripts\python.exe -m core.cli"
Write-Host ""
Write-Host "Dashboard startup depends on the dashboard server command configured by the project."
