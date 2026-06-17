# Repeatability (eval x3) — one command to remember: .\e.ps1
Set-Location $PSScriptRoot
python -m docs_code_drift_detector eval tests/fixtures/sample_project -o eval_out -n 3
