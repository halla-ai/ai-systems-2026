# Proposal S4 benchmark — 30 drift + 10 clean
# .\b.ps1                 full pipeline (no LLM)
# .\b.ps1 -LLM            full pipeline + LLM + semantic (needs OPENAI_API_KEY)
# .\b.ps1 -DetectionOnly  detection metrics only
Set-Location $PSScriptRoot

$useLlm = ($args -contains "-LLM") -or ($env:DRIFT_USE_LLM -eq "1")
$detectionOnly = $args -contains "-DetectionOnly"

$cliArgs = @("benchmark", "-o", "benchmark_out")
if ($useLlm) {
    $cliArgs += "--use-llm"
    $cliArgs += "--detect-semantic"
}
if ($detectionOnly) {
    $cliArgs += "--detection-only"
} else {
    $cliArgs += "--full-pipeline"
}

python -m docs_code_drift_detector @cliArgs
