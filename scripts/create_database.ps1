$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PasswordFile = Join-Path $ProjectRoot 'MySQL Root User Password.txt'
$MySqlExe = 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe'

if (-not (Test-Path -LiteralPath $MySqlExe)) {
    throw "MySQL client not found at $MySqlExe"
}

$env:MYSQL_PWD = (Get-Content -LiteralPath $PasswordFile -Raw).Trim()
try {
    & $MySqlExe --user=root --execute="CREATE DATABASE IF NOT EXISTS ai_detective CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to create or verify the ai_detective database.'
    }
}
finally {
    Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
}

Write-Host 'MySQL database ai_detective is ready.'
