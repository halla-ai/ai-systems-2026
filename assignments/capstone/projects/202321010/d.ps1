# Live demo — .\d.ps1  OR  .\d.ps1 <project-path>
# Output defaults to <project-path>/output
Set-Location $PSScriptRoot

$project = if ($args.Count -gt 0 -and $args[0]) { $args[0] } else { "testproject" }

python -m docs_code_drift_detector demo $project
