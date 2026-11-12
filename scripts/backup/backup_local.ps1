# Respaldo de la base local de desarrollo (Windows, PostgreSQL 18 instalado).
# Uso: powershell -ExecutionPolicy Bypass -File scripts\backup\backup_local.ps1
# Usa DB_* del .env. Programar con el Programador de tareas de Windows para un respaldo diario.
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$env_ = @{}
Get-Content (Join-Path $root '.env') | Where-Object { $_ -match '^\s*([A-Z_]+)\s*=\s*(.*)$' } | ForEach-Object {
    $env_[$Matches[1]] = ($Matches[2] -replace '\s+#.*$', '').Trim().Trim('"')
}
$bin = 'C:\Program Files\PostgreSQL\18\bin'
$dir = Join-Path $root 'backups'
New-Item -ItemType Directory -Force $dir | Out-Null
$file = Join-Path $dir ("{0}_{1}.dump" -f $env_['DB_NAME'], (Get-Date -Format 'yyyyMMdd-HHmmss'))
$env:PGPASSWORD = $env_['DB_PASSWORD']
& "$bin\pg_dump.exe" -h $env_['DB_HOST'] -p $env_['DB_PORT'] -U $env_['DB_USER'] -d $env_['DB_NAME'] --format=custom --compress=9 --no-owner --file=$file
if ($LASTEXITCODE -ne 0) { throw 'pg_dump falló' }
& "$bin\pg_restore.exe" --list $file | Out-Null
Remove-Item Env:PGPASSWORD
Get-ChildItem $dir -Filter '*.dump' | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } | Remove-Item
Write-Host ("Respaldo OK: {0} ({1:N1} MB)" -f $file, ((Get-Item $file).Length / 1MB)) -ForegroundColor Green
