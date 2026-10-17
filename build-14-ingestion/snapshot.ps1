# snapshot.ps1 - the facts the page is built from: the ledger (via the API), the quarantine listing with reasons, the poison and
# dead-letter containers/queues, Event Grid delivery metrics, and the last container run. Names only. -> data/ops_snapshot.json
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$acct = "stazportfoliob1"
$ledger = (Invoke-RestMethod "https://apim-azportfolio-b13.azure-api.net/data/ingest/ledger").data
$quar = az.cmd storage blob list --account-name $acct --auth-mode login -c quarantine --query "[].{name:name, size:properties.contentLength}" -o json | ConvertFrom-Json
$reasons = @{}
foreach ($b in $quar | Where-Object { $_.name -like "*.reason.txt" }) { $tmp = Join-Path $env:TEMP $b.name; az.cmd storage blob download --account-name $acct --auth-mode login -c quarantine -n $b.name -f $tmp --only-show-errors -o none; $reasons[$b.name] = (Get-Content $tmp -Raw).Trim(); Remove-Item $tmp }
$dead = az.cmd storage blob list --account-name $acct --auth-mode login -c deadletter --query "[].name" -o json | ConvertFrom-Json
$poison = az.cmd storage message peek --account-name $acct --auth-mode login -q ingest-load-poison --num-messages 10 -o json 2>$null | ConvertFrom-Json | ForEach-Object { $c = $_.content; try { $c = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($c)) } catch {}; @{ dequeueCount = $_.dequeueCount; content = $c } }
$tid = (az.cmd eventgrid system-topic show -n egst-stazportfoliob1 -g rg-azportfolio-b1 --query id -o tsv)
$eg = @{}
$m = az.cmd monitor metrics list --resource $tid --metric PublishSuccessCount,MatchedEventCount,DeliverySuccessCount,DeliveryAttemptFailCount,DeadLetteredCount --aggregation Total --interval PT1H --offset 1d -o json | ConvertFrom-Json
foreach ($v in $m.value) { $eg[$v.name.value] = ($v.timeseries[0].data | Where-Object { $null -ne $_.total } | Measure-Object -Property total -Sum).Sum }
$aci = az.cmd container show -n aci-azportfolio-b14 -g rg-azportfolio-b1 --query "{state:instanceView.state, exit:containers[0].instanceView.currentState.exitCode, started:containers[0].instanceView.currentState.startTime, finished:containers[0].instanceView.currentState.finishTime, image:containers[0].image}" -o json | ConvertFrom-Json
$log = (az.cmd container logs -n aci-azportfolio-b14 -g rg-azportfolio-b1 2>$null | Select-Object -Last 15) -join "`n"
$snap = [ordered]@{ taken_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"); ledger = $ledger; quarantine = $quar; quarantine_reasons = $reasons; deadletter = @($dead); poison = @($poison); eventgrid = $eg; aci = $aci; aci_log_tail = $log }
New-Item -ItemType Directory -Force (Join-Path $here "data") | Out-Null
$snap | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $here "data\ops_snapshot.json") -Encoding UTF8
Write-Output ("ledger " + @($ledger).Count + " rows; quarantine " + @($quar).Count + " blobs; deadletter " + @($dead).Count + "; poison " + @($poison).Count)
