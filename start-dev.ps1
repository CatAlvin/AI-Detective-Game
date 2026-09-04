$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot '.env'))) {
    & python (Join-Path $ProjectRoot 'scripts\setup_env.py')
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw 'Python environment is missing. Run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt'
}

$Backend = Start-Process -FilePath $PythonExe -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--reload', '--host', '127.0.0.1', '--port', '8765') -WorkingDirectory (Join-Path $ProjectRoot 'backend') -NoNewWindow -PassThru
$Frontend = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev') -WorkingDirectory (Join-Path $ProjectRoot 'frontend') -NoNewWindow -PassThru

Write-Host 'AI Detective Game is starting...'
Write-Host 'Frontend: http://127.0.0.1:5173'
Write-Host 'API docs: http://127.0.0.1:8765/api/docs'
Write-Host 'Press Ctrl+C to stop both services.'

try {
    while (-not $Backend.HasExited -and -not $Frontend.HasExited) {
        Start-Sleep -Seconds 1
        $Backend.Refresh()
        $Frontend.Refresh()
    }
}
finally {
    if (-not $Backend.HasExited) { Stop-Process -Id $Backend.Id }
    if (-not $Frontend.HasExited) { Stop-Process -Id $Frontend.Id }
}
