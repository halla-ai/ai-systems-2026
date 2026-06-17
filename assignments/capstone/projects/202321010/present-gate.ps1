# HOTL approve - use with present.ps1 step [5]
# Run in a 2nd PowerShell window

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root = $PSScriptRoot
Set-Location $Root

$Out = "testproject/output_wait"
if (-not (Test-Path "$Out\approval_gate.json")) {
    $Out = "testproject/output"
}

Write-Host "Approving gate: $Out" -ForegroundColor Cyan
python -m docs_code_drift_detector gate -o $Out approved
