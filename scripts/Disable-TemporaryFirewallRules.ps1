#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

Get-NetFirewallRule -DisplayName 'WireGuard GUI TEMP -*' -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule

Write-Output 'Temporary WireGuard GUI firewall rules removed.'
