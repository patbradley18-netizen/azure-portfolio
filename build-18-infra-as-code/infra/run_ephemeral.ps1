# Create → deploy → verify → delete, in one run. Group name carries the date so a failed delete is obvious. Cost: minutes of a
# storage account and a vault — fractions of a cent — and the group is deleted at the end whatever the verdict.
param([string]$Location = 'northcentralus')
$ErrorActionPreference = 'Stop'
$rg = 'rg-azportfolio-iac-test'
az.cmd group create -n $rg -l $Location -o none
try {
  $out = az.cmd deployment group create -g $rg -n ephemeral -f "$PSScriptRoot\ephemeral.bicep" --query "{state:properties.provisioningState, dur:properties.duration, o:properties.outputs}" -o json | ConvertFrom-Json
  Write-Output ("deploy " + $out.state + " in " + $out.dur)
  $sa = $out.o.storageAccount.value; $kv = $out.o.vault.value; $principal = $out.o.identityPrincipalId.value; $tp = $out.o.topic.value
  $evidence = @{
    storage    = (az.cmd storage account show -g $rg -n $sa -o json | ConvertFrom-Json)
    vault      = (az.cmd keyvault show -g $rg -n $kv -o json | ConvertFrom-Json)
    roles      = (az.cmd role assignment list --scope (az.cmd storage account show -g $rg -n $sa --query id -o tsv) -o json | ConvertFrom-Json)
    topic      = (az.cmd eventgrid system-topic show -g $rg -n $tp -o json | ConvertFrom-Json)
    # management plane (ARM), not data plane: shared key is off and the deployer holds no data role on the new account
    containers = (az.cmd storage container-rm list --storage-account $sa -g $rg -o json | ConvertFrom-Json)
    queues     = (az.cmd rest --method get --url ("https://management.azure.com" + (az.cmd storage account show -g $rg -n $sa --query id -o tsv) + "/queueServices/default/queues?api-version=2023-05-01") -o json | ConvertFrom-Json).value
    principalId = $principal
  }
  $json = $evidence | ConvertTo-Json -Depth 8
  [IO.File]::WriteAllText("$PSScriptRoot\..\data\ephemeral_evidence.json", $json)   # kept as the build's evidence (no secrets: names, flags, role names)
  $json | python -X utf8 "$PSScriptRoot\verify_ephemeral.py"
  $verdict = $LASTEXITCODE
} finally {
  # Windows PowerShell 5: with ErrorActionPreference=Stop, a native command's stderr warning THROWS — which once killed this
  # block after the vault delete and before the group delete. Clean-up must not be interruptible.
  $ErrorActionPreference = 'Continue'
  # a deleted Key Vault lingers soft-deleted for 7 days (name reserved, no charge): delete it explicitly and purge, then the group
  if ($kv) { az.cmd keyvault delete -n $kv -g $rg -o none 2>&1 | Out-Null; az.cmd keyvault purge -n $kv --no-wait -o none 2>&1 | Out-Null; Write-Output "vault $kv deleted and purge requested" }
  az.cmd group delete -n $rg --yes --no-wait -o none
  Write-Output "delete requested for $rg"
}
exit $verdict
