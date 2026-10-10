$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$pythonCandidates = @('python', 'py', (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'))
$pythonCommand = $null
foreach ($candidate in $pythonCandidates) {
    try {
        $version = & $candidate --version 2>$null
        if ($LASTEXITCODE -eq 0 -and $version -match 'Python 3\.(1[2-9]|[2-9][0-9])') { $pythonCommand = $candidate; break }
    } catch {}
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if (-not $pythonCommand) { throw 'Install Python 3.12+ from https://www.python.org/downloads/ and retry.' }
    & $pythonCommand -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
}
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath '.venv\ready.txt')) {
    & $venvPython -m pip install -r requirements.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check network and retry.' }
    Set-Content -LiteralPath '.venv\ready.txt' -Value '0.1.0' -Encoding UTF8
}
if (-not (Test-Path -LiteralPath 'web\dist\index.html')) {
    Push-Location -LiteralPath 'web'
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Node dependency installation failed.' }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
Write-Host 'Research Skills Workbench: http://127.0.0.1:8765'
Write-Host 'Keep this window open. Press Ctrl+C to stop.'
& $venvPython -m uvicorn server.main:app --host 127.0.0.1 --port 8765
