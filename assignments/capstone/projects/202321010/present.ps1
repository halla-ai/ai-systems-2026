# Docs-Code Drift Detector - presentation demo

# Usage: cd C:\Users\K\Desktop\기말  then  .\present.ps1



chcp 65001 | Out-Null

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$OutputEncoding = [System.Text.Encoding]::UTF8



$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot

Set-Location $Root



function Show-File([string]$Path, [int]$Lines = 30, [string]$Label = "") {

    if ($Label) { Write-Host "`n--- $Label ---" -ForegroundColor Yellow }

    python "$Root\present_show.py" $Path $Lines

}



function Step([string]$Title, [scriptblock]$Action) {

    Write-Host ""

    Write-Host "========================================" -ForegroundColor Cyan

    Write-Host " $Title" -ForegroundColor Cyan

    Write-Host "========================================" -ForegroundColor Cyan

    $r = Read-Host "Enter=run, s=skip, q=quit"

    if ($r -eq "q") { exit 0 }

    if ($r -eq "s") { Write-Host "(skipped)" -ForegroundColor DarkGray; return }

    & $Action

}



Write-Host @"



  Docs-Code Drift Detector - LIVE DEMO

  ------------------------------------

  One command shows the full pipeline + evidence summary.

  Press Enter each step. Korean text: use Notepad (step 2 opens files).



"@ -ForegroundColor Green



Step "1/4 Main demo (one command + HOTL prompt)" {
    Write-Host "  After RUN EVIDENCE: Enter=PR, n=revise, q=quit" -ForegroundColor Yellow
    python -m docs_code_drift_detector demo testproject -o testproject/output
}



Step "2/4 Show artifacts (UTF-8 safe)" {

    Show-File "testproject\output\drift_report.json" 0 "drift_report summary"

    Show-File "testproject\output\patch.diff" 25 "patch.diff"

    Show-File "testproject\output\pr_dry_run.txt" 35 "pr_dry_run.txt"

    Write-Host "`nOpening patch.diff and pr_dry_run.txt in Notepad (Korean OK there)..." -ForegroundColor Green

    Start-Process notepad.exe "testproject\output\patch.diff"

    Start-Sleep -Milliseconds 500

    Start-Process notepad.exe "testproject\output\pr_dry_run.txt"

}



Step "3/4 HOTL wait (--wait-hotl) - THIS window" {

    Write-Host @"



  >>> Open another PowerShell window:

      cd $Root

      .\present-gate.ps1



"@ -ForegroundColor Yellow

    Read-Host "Ready? Press Enter"

    python -m docs_code_drift_detector demo testproject -o testproject/output_wait --wait-hotl --wait-hotl-timeout 120

}



Step "4/4 Optional: repeatability proof (eval x3)" {

    python -m docs_code_drift_detector eval tests/fixtures/sample_project -o eval_out -n 3

    Show-File "eval_out\eval_summary.json" 15 "eval_summary (first 15 lines)"

}



Write-Host @"



  Bonus (skip if time short): real GitHub PR

    python -m docs_code_drift_detector demo testproject -o testproject/output_pr --create-pr



"@ -ForegroundColor DarkGray



Write-Host "`nDemo finished.`n" -ForegroundColor Green

