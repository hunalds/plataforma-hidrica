# Verificación completa del proyecto antes de cada commit (HU-0.7).
# Uso (desde la raíz del proyecto):
#   powershell -ExecutionPolicy Bypass -File scripts\check.ps1            # todo
#   powershell -ExecutionPolicy Bypass -File scripts\check.ps1 -Only backend,ml
# Requiere: uv, Node.js y PostgreSQL local en marcha (las pruebas del backend usan la base de pruebas).
param(
    [ValidateSet('backend', 'ml', 'frontend')]
    [string[]]$Only = @('backend', 'ml', 'frontend')
)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')

# uv instalado con winget no siempre está en el PATH de la sesión
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    $uvDir = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Directory -Filter 'astral-sh.uv*' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($uvDir) { $env:Path = "$($uvDir.FullName);$env:Path" } else { throw 'No se encontró uv. Instálalo con: winget install astral-sh.uv' }
}

$results = [ordered]@{}
function Invoke-Step([string]$name, [string]$dir, [scriptblock]$cmd) {
    Write-Host "`n=== $name ===" -ForegroundColor Cyan
    Push-Location (Join-Path $root $dir)
    try {
        & $cmd
        $ok = ($LASTEXITCODE -eq 0)
    } catch {
        Write-Host $_ -ForegroundColor Red
        $ok = $false
    } finally {
        Pop-Location
    }
    $script:results[$name] = $ok
}

if ($Only -contains 'backend') {
    Invoke-Step 'backend · ruff' 'backend' { uv run ruff check . ../scripts; if ($LASTEXITCODE -eq 0) { uv run ruff format --check . ../scripts } }
    Invoke-Step 'backend · pytest' 'backend' { uv run pytest }
}
if ($Only -contains 'ml') {
    Invoke-Step 'ml · ruff' 'ml' { uv run ruff check .; if ($LASTEXITCODE -eq 0) { uv run ruff format --check . } }
    Invoke-Step 'ml · pytest' 'ml' { uv run pytest }
}
if ($Only -contains 'frontend') {
    if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
        Push-Location (Join-Path $root 'frontend'); npm ci --no-fund --no-audit; Pop-Location
    }
    Invoke-Step 'frontend · eslint' 'frontend' { npx eslint . }
    Invoke-Step 'frontend · tsc' 'frontend' { npx tsc -b --noEmit }
    Invoke-Step 'frontend · vitest' 'frontend' { npx vitest run }
}

Write-Host "`n=== Resumen ===" -ForegroundColor Cyan
$failed = 0
foreach ($k in $results.Keys) {
    if ($results[$k]) { Write-Host "  OK     $k" -ForegroundColor Green } else { Write-Host "  FALLA  $k" -ForegroundColor Red; $failed++ }
}
if ($failed -gt 0) { Write-Host "`n$failed paso(s) fallaron." -ForegroundColor Red; exit 1 }
Write-Host "`nTodo en verde." -ForegroundColor Green
