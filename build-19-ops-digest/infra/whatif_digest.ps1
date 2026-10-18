# Build #19 step A: compile and preview only. Nothing is created here.
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$rg = 'rg-azportfolio-b1'
az.cmd bicep build --file "$here\digest.bicep" --stdout > $null
"build exit: $LASTEXITCODE"
az.cmd deployment group what-if -g $rg -n b19-digest-1 --template-file "$here\digest.bicep" --no-pretty-print -o json > "$env:TEMP\b19_whatif.json"
"what-if exit: $LASTEXITCODE"
$w = Get-Content "$env:TEMP\b19_whatif.json" -Raw | ConvertFrom-Json
$w.changes | ForEach-Object { $_.changeType + '  ' + ($_.resourceId -replace '^/subscriptions/[^/]+', '') }
"done"
