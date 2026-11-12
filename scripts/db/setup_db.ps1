# Crea el usuario y las bases de la Plataforma Hídrica y activa PostGIS.
# Uso (desde la raíz del proyecto):
#   powershell -ExecutionPolicy Bypass -File scripts\db\setup_db.ps1
# Te pedirá la contraseña del superusuario "postgres". No se guarda en ningún lado.
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$envFile = Join-Path $root '.env'
if (-not (Test-Path $envFile)) { throw "No existe $envFile. Copia .env.example como .env y completa DB_PASSWORD." }

$line = Get-Content $envFile | Where-Object { $_ -match '^\s*DB_PASSWORD\s*=' } | Select-Object -First 1
if (-not $line) { throw 'DB_PASSWORD no está definido en .env' }
$appPassword = ($line -replace '^\s*DB_PASSWORD\s*=\s*', '').Trim().Trim('"').Trim("'")
if ($appPassword -eq 'cambia-esta-contrasena' -or $appPassword.Length -lt 8) { throw 'Define una DB_PASSWORD real (mínimo 8 caracteres) en .env' }

$psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
if (-not (Test-Path $psql)) { $psql = 'psql' }

& $psql -U postgres -h localhost -d postgres -v "app_password=$appPassword" -f (Join-Path $PSScriptRoot 'setup_db.sql')
if ($LASTEXITCODE -ne 0) { throw "psql terminó con código $LASTEXITCODE" }
Write-Host "`nBase de datos lista. Verifica con: uv run --project backend python scripts/check_db.py" -ForegroundColor Green
