# Ejecutar desde fuera del proyecto, después de cerrar editores que bloqueen su carpeta.
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)][string]$Source,
    [string]$Name = 'once',
    [int]$WaitForProcessId = 0,
    [string]$LogPath
)

$ErrorActionPreference = 'Stop'
try {
    $onceSource = (Resolve-Path -LiteralPath $Source).Path.TrimEnd('\')
    $onceParent = Split-Path -Parent $onceSource
    if (!$Name -or [IO.Path]::GetFileName($Name) -ne $Name -or $Name -in @('.', '..')) {
        throw 'El destino debe ser un nombre de carpeta, sin rutas.'
    }
    $onceTarget = [IO.Path]::GetFullPath((Join-Path $onceParent $Name))
    $onceItem = Get-Item -LiteralPath $onceSource
    if (!$onceItem.PSIsContainer -or $onceItem.LinkType -or
        (Split-Path -Parent $onceTarget) -ne $onceParent -or
        (Test-Path -LiteralPath $onceTarget)) {
        throw 'Origen o destino inesperado. No se movió ningún archivo.'
    }
    $onceCompose = Join-Path $onceSource 'docker-compose.yml'
    if (!(Test-Path -LiteralPath (Join-Path $onceSource '.git')) -or
        !(Test-Path -LiteralPath $onceCompose) -or
        !([IO.File]::ReadAllText($onceCompose) -match '(?m)^name: vertice\s*$')) {
        throw 'No se reconoce el proyecto o su identidad persistente de Docker.'
    }
    if ($PSCmdlet.ShouldProcess($onceSource, "Renombrar como $onceTarget")) {
        Set-Location -LiteralPath $onceParent
        if ($WaitForProcessId -gt 0 -and (Get-Process -Id $WaitForProcessId -ErrorAction SilentlyContinue)) {
            Wait-Process -Id $WaitForProcessId -Timeout 900
        }
        Move-Item -LiteralPath $onceSource -Destination $onceTarget
        if (!(Test-Path -LiteralPath (Join-Path $onceTarget 'docker-compose.yml'))) {
            throw 'No se pudo verificar la carpeta de destino.'
        }
        $onceMessage = "Renombrado completado: $onceTarget. Docker conserva el proyecto vertice y su volumen. Abre esta carpeta en tu editor."
        if ($LogPath) { [IO.File]::WriteAllText($LogPath, $onceMessage) }
        Write-Output $onceMessage
    }
} catch {
    if ($LogPath) { [IO.File]::WriteAllText($LogPath, "No se completó el renombrado: $($_.Exception.Message)") }
    throw
}
