# Build #19: read-only snapshot for the page. Saves names and counts only: no email, no subscription id, no GUIDs.
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$data = Join-Path $here 'data'; New-Item -ItemType Directory -Force -Path $data | Out-Null
function Save($name, $obj) { [IO.File]::WriteAllText((Join-Path $data $name), ($obj | ConvertTo-Json -Depth 8)) }
$sub = az.cmd account show --query id -o tsv
$rg = 'rg-azportfolio-b1'
$wf = "https://management.azure.com/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.Logic/workflows/la-azportfolio-digest"

# 1. Every digest run so far, and the digest each one wrote (from the run's own Digest action)
$runs = (az.cmd rest --method get --url "$wf/runs?api-version=2016-06-01" -o json | ConvertFrom-Json).value
$out = @()
foreach ($r in $runs) {
  $acts = (az.cmd rest --method get --url "$wf/runs/$($r.name)/actions?api-version=2016-06-01" -o json | ConvertFrom-Json).value
  $d = $acts | Where-Object { $_.name -eq 'Digest' }
  $digest = $null; if ($d.properties.outputsLink) { $digest = Invoke-RestMethod $d.properties.outputsLink.uri }
  $out += [pscustomobject]@{ run = $r.name; status = $r.properties.status; start = $r.properties.startTime; end = $r.properties.endTime
    actions = @($acts | Sort-Object name | ForEach-Object { [pscustomobject]@{ name = $_.name; status = $_.properties.status; code = $_.properties.code } })
    digest = $digest }
}
Save 'digest_runs.json' @($out)

# 2. Failed Function requests, 7 days, with the exception type
$ws = "/subscriptions/$sub/resourceGroups/DefaultResourceGroup-DEWC/providers/Microsoft.OperationalInsights/workspaces/DefaultWorkspace-$sub-DEWC"
$q = @{ query = "AppRequests | where TimeGenerated > ago(7d) and Success == false | join kind=leftouter (AppExceptions | where TimeGenerated > ago(7d) | summarize err=take_any(ExceptionType) by OperationId) on OperationId | summarize n=sum(ItemCount), t0=min(TimeGenerated), t1=max(TimeGenerated), err=take_any(err) by app=AppRoleName, fn=Name, code=ResultCode | order by app asc, n desc" } | ConvertTo-Json -Compress
[IO.File]::WriteAllText("$env:TEMP\kq.json", $q)
$r = az.cmd rest --method post --url "https://management.azure.com$ws/api/query?api-version=2020-08-01" --body "@$env:TEMP\kq.json" -o json | ConvertFrom-Json
Save 'function_failures_7d.json' $r.tables[0]   # columns + rows; build_findings.py zips them

# 3. GitHub workflow failures (public API)
$g = Invoke-RestMethod 'https://api.github.com/repos/patbradley18-netizen/azure-portfolio/actions/runs?per_page=100' -Headers @{ 'User-Agent' = 'azportfolio-snapshot' }
Save 'github_failures.json' @($g.workflow_runs | Where-Object { $_.conclusion -eq 'failure' } | ForEach-Object { [pscustomobject]@{ workflow = $_.name; created = $_.created_at; sha = $_.head_sha.Substring(0,7); title = $_.display_title } })

# 4. Alerts and their state (names only)
$al = az.cmd monitor metrics alert list -g $rg -o json | ConvertFrom-Json
Save 'alerts.json' @($al | ForEach-Object { [pscustomobject]@{ name = $_.name; enabled = $_.enabled; severity = $_.severity; window = $_.windowSize; every = $_.evaluationFrequency; metric = $_.criteria.allOf[0].metricName; threshold = $_.criteria.allOf[0].threshold } })

# 5. main.bicep what-if with the b19 module: change type, resource type, property paths (GUID names dropped)
$w = Get-Content "$env:TEMP\b19_main_whatif.json" -Raw | ConvertFrom-Json
Save 'whatif_main.json' @($w.changes | ForEach-Object { $seg = $_.resourceId.Split('/'); $t = $seg[-2]; $n = if ($seg[-1] -match '^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$') { '(guid name)' } else { $seg[-1] }
  [pscustomobject]@{ change = $_.changeType; type = $t; name = $n; paths = (($_.delta | ForEach-Object { $_.path }) -join ', ') } })
# 6. Alerts that fired in the last 7 days (rule name, condition, time)
$fa = az.cmd rest --method get --url "https://management.azure.com/subscriptions/$sub/providers/Microsoft.AlertsManagement/alerts" --uri-parameters api-version=2019-05-05-preview timeRange=7d -o json | ConvertFrom-Json
Save 'fired_alerts.json' @($fa.value | ForEach-Object { [pscustomobject]@{ rule = $_.properties.essentials.alertRule.Split('/')[-1]; condition = $_.properties.essentials.monitorCondition; fired = $_.properties.essentials.startDateTime } })
"saved: " + ((Get-ChildItem $data).Name -join ', ')
