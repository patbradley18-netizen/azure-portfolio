# snapshot.ps1 - saves the operational facts the page is built from: the SQL free-limit metric series (30 days, hourly),
# the alert rule as it stands, the fired-alert records, and the action group (names only). -> data/ops_snapshot.json
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$sub = (az.cmd account show --query id -o tsv)
$dbid = (az.cmd sql db show -g rg-azportfolio-b1 -s sql-azportfolio-b1eu -n aid --query id -o tsv)
$metrics = az.cmd monitor metrics list --resource $dbid --metric free_amount_consumed,free_amount_remaining,app_cpu_billed --aggregation Maximum --interval PT1H --offset 30d -o json | ConvertFrom-Json
$series = @{}
foreach ($m in $metrics.value) { $series[$m.name.value] = @($m.timeseries[0].data | Where-Object { $null -ne $_.maximum } | ForEach-Object { @{ t = $_.timeStamp; v = $_.maximum } }) }
$rule = az.cmd monitor metrics alert show -n alert-sql-free-limit -g rg-azportfolio-b1 --query "{name:name, enabled:enabled, severity:severity, window:windowSize, freq:evaluationFrequency, metric:criteria.allOf[0].metricName, op:criteria.allOf[0].operator, threshold:criteria.allOf[0].threshold, agg:criteria.allOf[0].timeAggregation}" -o json | ConvertFrom-Json
$fired = az.cmd rest --method get --url "https://management.azure.com/subscriptions/$sub/providers/Microsoft.AlertsManagement/alerts" --url-parameters "api-version=2019-05-05-preview" "timeRange=7d" --query "value[].{name:name, severity:properties.essentials.severity, state:properties.essentials.monitorCondition, fired:properties.essentials.startDateTime, resolved:properties.essentials.monitorConditionResolvedDateTime, target:properties.essentials.targetResourceName, signal:properties.essentials.signalType}" -o json | ConvertFrom-Json
$ag = az.cmd monitor action-group show -n ag-azportfolio-ops -g rg-azportfolio-b1 --query "{name:name, shortName:groupShortName, emailReceivers:length(emailReceivers)}" -o json | ConvertFrom-Json
$snap = [ordered]@{ taken_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"); free_limit_month = 100000; metrics = $series; alert_rule = $rule; fired_alerts = @($fired); action_group = $ag }
New-Item -ItemType Directory -Force (Join-Path $here "data") | Out-Null
$snap | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $here "data\ops_snapshot.json") -Encoding UTF8
Write-Output ("consumed points " + $series['free_amount_consumed'].Count + "; fired alerts " + @($fired).Count)
