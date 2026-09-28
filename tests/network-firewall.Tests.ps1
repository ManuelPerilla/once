# Pester 3.4+: todas las operaciones NetSecurity se sustituyen antes de invocar el asistente.
$helper = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\network-firewall.ps1'
. $helper -Action Enable -Port 80

Describe 'Regla de firewall local de ONCE' {
    BeforeEach {
        $script:onceRules = @()
        Mock Test-OnceAdministrator { $true }
        Mock Get-NetFirewallRule { $script:onceRules }
        Mock New-NetFirewallRule {
            $script:onceRules += [pscustomobject]@{ Name = $Name; Group = $Group }
        }
        Mock Set-NetFirewallRule {}
        Mock Remove-NetFirewallRule {}
    }

    It 'crea una sola regla del puerto pedido y la actualiza al repetir' {
        Set-OnceLanFirewall -Action Enable -Port 8080
        Set-OnceLanFirewall -Action Enable -Port 8080
        Assert-MockCalled New-NetFirewallRule -Times 1 -Exactly -Scope It -ParameterFilter {
            $Name -eq 'ONCE-LAN-HTTP-8080' -and $Group -eq 'ONCE Local Network' -and
            $PolicyStore -eq 'PersistentStore' -and $Direction -eq 'Inbound' -and
            $Action -eq 'Allow' -and $Profile -eq 'Any' -and $Enabled -eq 'True' -and
            $Protocol -eq 'TCP' -and $LocalPort -eq 8080 -and
            $RemoteAddress -eq 'LocalSubnet' -and $EdgeTraversalPolicy -eq 'Block'
        }
        Assert-MockCalled Set-NetFirewallRule -Times 1 -Exactly -Scope It -ParameterFilter {
            $Name -eq 'ONCE-LAN-HTTP-8080' -and $PolicyStore -eq 'PersistentStore' -and
            $Direction -eq 'Inbound' -and $Action -eq 'Allow' -and $Profile -eq 'Any' -and
            $Protocol -eq 'TCP' -and $LocalPort -eq 8080 -and $RemoteAddress -eq 'LocalSubnet'
        }
        Assert-MockCalled Remove-NetFirewallRule -Times 0 -Exactly -Scope It
    }

    It 'retira solo el nombre exacto del puerto y grupo de ONCE' {
        $script:onceRules = @(
            [pscustomobject]@{ Name = 'ONCE-LAN-HTTP-80'; Group = 'ONCE Local Network' },
            [pscustomobject]@{ Name = 'ONCE-LAN-HTTP-8080'; Group = 'ONCE Local Network' },
            [pscustomobject]@{ Name = 'Otra-regla'; Group = 'Otro grupo' }
        )
        Set-OnceLanFirewall -Action Disable -Port 80
        Assert-MockCalled Remove-NetFirewallRule -Times 1 -Exactly -Scope It -ParameterFilter {
            $Name -eq 'ONCE-LAN-HTTP-80' -and $PolicyStore -eq 'PersistentStore'
        }
        Assert-MockCalled Remove-NetFirewallRule -Times 1 -Exactly -Scope It
        Assert-MockCalled New-NetFirewallRule -Times 0 -Exactly -Scope It
        Assert-MockCalled Set-NetFirewallRule -Times 0 -Exactly -Scope It
    }

    It 'no cambia nada al retirar una regla inexistente' {
        Set-OnceLanFirewall -Action Disable -Port 80
        Assert-MockCalled Remove-NetFirewallRule -Times 0 -Exactly -Scope It
    }

    It 'rechaza una colision de nombre fuera del grupo tanto al crear como al retirar' {
        $script:onceRules = @([pscustomobject]@{ Name = 'ONCE-LAN-HTTP-80'; Group = 'Ajeno' })
        { Set-OnceLanFirewall -Action Enable -Port 80 } | Should Throw
        { Set-OnceLanFirewall -Action Disable -Port 80 } | Should Throw
        Assert-MockCalled New-NetFirewallRule -Times 0 -Exactly -Scope It
        Assert-MockCalled Set-NetFirewallRule -Times 0 -Exactly -Scope It
        Assert-MockCalled Remove-NetFirewallRule -Times 0 -Exactly -Scope It
    }

    It 'rechaza duplicados sin alterarlos' {
        $script:onceRules = @(
            [pscustomobject]@{ Name = 'ONCE-LAN-HTTP-80'; Group = 'ONCE Local Network' },
            [pscustomobject]@{ Name = 'ONCE-LAN-HTTP-80'; Group = 'ONCE Local Network' }
        )
        { Set-OnceLanFirewall -Action Enable -Port 80 } | Should Throw
        Assert-MockCalled Set-NetFirewallRule -Times 0 -Exactly -Scope It
    }

    It 'requiere administrador antes de consultar o cambiar reglas' {
        Mock Test-OnceAdministrator { $false }
        { Set-OnceLanFirewall -Action Enable -Port 80 } | Should Throw
        Assert-MockCalled Get-NetFirewallRule -Times 0 -Exactly -Scope It
        Assert-MockCalled New-NetFirewallRule -Times 0 -Exactly -Scope It
        Assert-MockCalled Set-NetFirewallRule -Times 0 -Exactly -Scope It
        Assert-MockCalled Remove-NetFirewallRule -Times 0 -Exactly -Scope It
    }

    It 'rechaza puertos fuera del rango antes de consultar reglas' {
        { Set-OnceLanFirewall -Action Enable -Port 0 } | Should Throw
        { Set-OnceLanFirewall -Action Enable -Port 65536 } | Should Throw
        Assert-MockCalled Get-NetFirewallRule -Times 0 -Exactly -Scope It
    }

    It 'no crea reglas cuando no puede leer el firewall' {
        Mock Get-NetFirewallRule { throw 'Consulta no disponible' }
        { Set-OnceLanFirewall -Action Enable -Port 80 } | Should Throw
        Assert-MockCalled New-NetFirewallRule -Times 0 -Exactly -Scope It
    }
}
