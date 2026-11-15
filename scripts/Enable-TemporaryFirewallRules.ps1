#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

$rules = @(
    @{
        DisplayName = 'WireGuard GUI TEMP - Inbound UDP 51820'
        Direction = 'Inbound'
    },
    @{
        DisplayName = 'WireGuard GUI TEMP - Outbound UDP 51820'
        Direction = 'Outbound'
    }
)

foreach ($rule in $rules) {
    if (-not (Get-NetFirewallRule -DisplayName $rule.DisplayName -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule `
            -DisplayName $rule.DisplayName `
            -Group 'WireGuard GUI Temporary' `
            -Description 'Temporary test rule for WireGuard GUI; remove after connectivity test.' `
            -Direction $rule.Direction `
            -Action Allow `
            -Protocol UDP `
            -LocalPort 51820 `
            -Profile Any | Out-Null
    }
}

Get-NetFirewallRule -DisplayName 'WireGuard GUI TEMP -*' |
    Select-Object DisplayName, Enabled, Direction, Action, Profile
