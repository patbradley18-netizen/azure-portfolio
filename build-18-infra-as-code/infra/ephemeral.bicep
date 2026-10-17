// Ephemeral proof module: the free pieces of the portfolio's pattern, deployable into a throw-away resource group and deleted
// by the same workflow. Storage (LRS, no public access) + inbox/quarantine containers + a work queue, a Key Vault (RBAC), a
// user-assigned identity, two scoped role assignments, and an Event Grid system topic on the storage account. No SQL, no
// Function plan, no APIM: those are either one-per-subscription free offers or throttled, and this group exists for minutes.
@description('Per-run suffix: a deleted storage account keeps its name reserved for a while, so each run gets its own (utcNow is only allowed in a parameter default).')
param runStamp string = utcNow('yyyyMMddHHmmss')
@minLength(3)
param suffix string = uniqueString(resourceGroup().id, runStamp)
param location string = resourceGroup().location

var storageName = 'stiac${suffix}'
var vaultName = 'kv-iac-${suffix}'
var roleBlobDataContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var roleQueueDataContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { minimumTlsVersion: 'TLS1_2', allowBlobPublicAccess: false, supportsHttpsTrafficOnly: true, allowSharedKeyAccess: false }
}
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = { parent: storage, name: 'default' }
resource inbox 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = { parent: blobs, name: 'inbox', properties: { publicAccess: 'None' } }
resource quarantine 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = { parent: blobs, name: 'quarantine', properties: { publicAccess: 'None' } }
resource queues 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = { parent: storage, name: 'default' }
resource workQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = { parent: queues, name: 'ingest-load' }

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-iac-${suffix}'
  location: location
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

// guid() names are fine HERE: this template creates the assignments, so it also owns their names.
resource raBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, roleBlobDataContributor)
  scope: storage
  properties: { roleDefinitionId: roleBlobDataContributor, principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
}
resource raQueue 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, roleQueueDataContributor)
  scope: storage
  properties: { roleDefinitionId: roleQueueDataContributor, principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
}

resource topic 'Microsoft.EventGrid/systemTopics@2024-06-01-preview' = {
  name: 'egst-${storageName}'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: { source: storage.id, topicType: 'Microsoft.Storage.StorageAccounts' }
}

output storageAccount string = storage.name
output vault string = vault.name
output identityPrincipalId string = identity.properties.principalId
output topic string = topic.name
