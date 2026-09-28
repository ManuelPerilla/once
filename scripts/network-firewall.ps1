# Invocado solo cuando se solicita --firewall. No eleva permisos automaticamente.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Enable', 'Disable')]
    [string]$Action,
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 65535)]
    [int]$Port
)

function Test-OnceAdministrator {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Este asistente de firewall requiere Windows.'
    }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Set-OnceLanFirewall {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('Enable', 'Disable')]
        [string]$Action,
        [Parameter(Mandatory = $true)]
        [ValidateRange(1, 65535)]
        [int]$Port
    )

    if (-not (Test-OnceAdministrator)) {
        throw 'Para cambiar la regla de ONCE, abre PowerShell como administrador y repite con --firewall. Sin esa opcion puedes iniciar ONCE normalmente.'
    }
    $group = 'ONCE Local Network'
    $name = "ONCE-LAN-HTTP-$Port"
    # Una consulta fallida no debe confundirse con una regla ausente.
    $rules = @(Get-NetFirewallRule -PolicyStore PersistentStore -ErrorAction Stop |
        Where-Object { $_.Name -eq $name })
    if ($rules | Where-Object { $_.Group -ne $group }) {
        throw "Ya existe $name fuera del grupo de ONCE. No se modifico ninguna regla."
    }
    if ($rules.Count -gt 1) {
        throw "Hay reglas duplicadas para $name. No se modifico ninguna regla."
    }

    if ($Action -eq 'Disable') {
        if ($rules.Count -eq 1) {
            Remove-NetFirewallRule -Name $name -PolicyStore PersistentStore -ErrorAction Stop
        }
        Write-Output "Regla de ONCE para el puerto $Port retirada o ya ausente."
        return
    }

    $filters = @{
        Enabled = 'True'
        Direction = 'Inbound'
        Action = 'Allow'
        Profile = 'Any'
        Protocol = 'TCP'
        LocalPort = $Port
        RemotePort = 'Any'
        LocalAddress = 'Any'
        RemoteAddress = 'LocalSubnet'
        Program = 'Any'
        Service = 'Any'
        InterfaceType = 'Any'
        EdgeTraversalPolicy = 'Block'
        ErrorAction = 'Stop'
    }
    if ($rules.Count -eq 1) {
        Set-NetFirewallRule -Name $name -PolicyStore PersistentStore @filters | Out-Null
    } else {
        New-NetFirewallRule -Name $name -Group $group -PolicyStore PersistentStore `
            -DisplayName "ONCE - Red local TCP $Port" @filters | Out-Null
    }
    Write-Output "ONCE permite TCP $Port solo desde la subred local."
}

# Permite cargar las funciones en las pruebas sin consultar ni cambiar el firewall.
if ($MyInvocation.InvocationName -ne '.') {
    Set-OnceLanFirewall -Action $Action -Port $Port
}
