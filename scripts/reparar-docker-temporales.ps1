# Recuperacion reversible del fallo de sockets de Docker Desktop en Windows.
# Cierra Docker Desktop antes de ejecutar. No elimina discos ni volumenes.
[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'
$onceActive = Get-Process -Name 'Docker Desktop', 'com.docker.backend', 'com.docker.build', 'docker-desktop' -ErrorAction SilentlyContinue
if ($onceActive) {
    throw 'Cierra Docker Desktop (Quit) y sus comandos de arranque antes de ejecutar la reparacion.'
}

$onceLocal = [IO.Path]::GetFullPath($env:LOCALAPPDATA)
$onceTargets = @(
    (Join-Path $onceLocal 'Docker\run'),
    (Join-Path $onceLocal 'docker-secrets-engine')
)
$onceAllowed = @(
    'dockerEthernetVfkit', 'dockerEthernetVfkit.stale',
    'dockerInference', 'dockerInference.stale',
    'sailor-ingest.sock', 'sailor-ingest.sock.stale',
    'userAnalyticsOtlpHttp.sock', 'userAnalyticsOtlpHttp.sock.stale',
    'engine.sock', 'engine.sock.stale'
)

# Validar todas las rutas antes de renombrar ninguna. No seguir enlaces.
foreach ($onceTarget in $onceTargets) {
    $onceItem = Get-Item -LiteralPath $onceTarget
    if ($onceItem.FullName -ne $onceTarget -or -not $onceItem.PSIsContainer -or
        ($onceItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Ruta temporal inesperada: $onceTarget"
    }
    foreach ($onceEntry in (Get-ChildItem -LiteralPath $onceTarget -Force)) {
        if ($onceEntry.PSIsContainer -or $onceEntry.Name -notin $onceAllowed -or $onceEntry.Length -ne 0) {
            throw "Contenido inesperado en $onceTarget. No se modifico ninguna carpeta."
        }
    }
}

$onceStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
if ($PSCmdlet.ShouldProcess(($onceTargets -join ', '), 'Conservar temporales en carpetas de respaldo y crear carpetas vacias')) {
    foreach ($onceTarget in $onceTargets) {
        $onceItem = Get-Item -LiteralPath $onceTarget
        $onceBackupName = $onceItem.Name + '.before-once-repair-' + $onceStamp
        $onceBackupPath = Join-Path $onceItem.Parent.FullName $onceBackupName
        if (Test-Path -LiteralPath $onceBackupPath) { throw "Ya existe $onceBackupPath" }
        Rename-Item -LiteralPath $onceTarget -NewName $onceBackupName
        New-Item -ItemType Directory -Path $onceTarget | Out-Null
        Write-Output "Respaldo conservado: $onceBackupPath"
    }
    Write-Output 'Listo. Abre Docker Desktop y despues ejecuta iniciar-once.cmd.'
}
