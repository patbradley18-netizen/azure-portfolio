# run_kql.ps1 - runs every kql/K*.kql against the portfolio's Log Analytics workspace and saves data/kql_results.json.
# Names only: the workspace is looked up by name; its customer id is read at run time and never written down.
# Run from the repo folder on the PC: powershell -ExecutionPolicy Bypass -File build-12-operations\run_kql.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ws = (az.cmd monitor log-analytics workspace show -g DefaultResourceGroup-DEWC -n DefaultWorkspace-9cb921f7-8a0b-445c-bb35-eca47da1daae-DEWC --query customerId -o tsv)
$out = [ordered]@{}
foreach ($f in Get-ChildItem (Join-Path $here "kql") -Filter "K*.kql" | Sort-Object Name) {
  $text = Get-Content $f.FullName -Raw
  $title = ($text -split "`n")[0].TrimStart("/ ").Trim()
  $q = ((($text -split "`n") | Where-Object { $_ -notmatch "^\s*//" }) | ForEach-Object { $_.Trim() }) -join " "   # one line: newlines do not survive the argument
  $json = az.cmd monitor log-analytics query -w $ws --analytics-query "$q" --timespan P90D -o json 2>$null
  $rows = if ($json) { $json | ConvertFrom-Json } else { @() }
  $out[$f.BaseName] = [ordered]@{ title = $title; kql = $q; rows = $rows }
  Write-Output ("{0}: {1} rows" -f $f.BaseName, @($rows).Count)
}
New-Item -ItemType Directory -Force (Join-Path $here "data") | Out-Null
$out | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $here "data\kql_results.json") -Encoding UTF8
Write-Output "saved data\kql_results.json"
