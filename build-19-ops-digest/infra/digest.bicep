// Build #19: operations round two — the weekly digest.
// Logic App (Consumption) with a system-assigned identity gathers six health checks, writes digest.json to Blob,
// and emails a red/amber/green summary through Azure Communication Services Email. No keys anywhere:
// every call is an Entra token for the Logic App's own identity. The recipient is read at run time from the
// action group, so no email address is in this file, the workflow definition, or the repo.
// Deployed into rg-azportfolio-b1 as a module of build-10-va-access/infra/main.bicep.

param location string = 'northcentralus'
param storageName string = 'stazportfoliob1'
param sqlServerName string = 'sql-azportfolio-b1eu'
param sqlDbName string = 'aid'
param actionGroupName string = 'ag-azportfolio-ops'
param workspaceResourceGroup string = 'DefaultResourceGroup-DEWC'
param workspaceName string = 'DefaultWorkspace-${subscription().subscriptionId}-DEWC'
param repo string = 'patbradley18-netizen/azure-portfolio'
param adxExpiry string = '2027-10-17'
param budgetUsd int = 10
param sqlFreeLimit int = 100000
param functionApps array = [ 'func-azportfolio-b1', 'func-azportfolio-b2', 'func-azportfolio-b13', 'func-azportfolio-b14' ]

// ---------- Azure Communication Services Email ----------
resource emailService 'Microsoft.Communication/emailServices@2023-04-01' = {
  name: 'ecs-azportfolio'
  location: 'global'
  properties: { dataLocation: 'United States' }
}

resource emailDomain 'Microsoft.Communication/emailServices/domains@2023-04-01' = {
  parent: emailService
  name: 'AzureManagedDomain'
  location: 'global'
  properties: { domainManagement: 'AzureManaged', userEngagementTracking: 'Disabled' }
}

resource acs 'Microsoft.Communication/communicationServices@2023-04-01' = {
  name: 'acs-azportfolio'
  location: 'global'
  properties: { dataLocation: 'United States', linkedDomains: [ emailDomain.id ] }
}

// ---------- Where the digest history lives ----------
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = { name: storageName }
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' existing = { parent: storage, name: 'default' }
resource queues 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' existing = { parent: storage, name: 'default' }
resource quarantine 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = { parent: blobs, name: 'quarantine' }
resource deadletter 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = { parent: blobs, name: 'deadletter' }
resource poisonQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' existing = { parent: queues, name: 'ingest-load-poison' }

resource opsdigest 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'opsdigest'
  properties: { publicAccess: 'None', defaultEncryptionScope: '$account-encryption-key', denyEncryptionScopeOverride: false }
}

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' existing = { name: sqlServerName }
resource sqlDb 'Microsoft.Sql/servers/databases@2023-08-01-preview' existing = { parent: sqlServer, name: sqlDbName }
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' existing = { name: actionGroupName }

// ---------- The Logic App ----------
resource digest 'Microsoft.Logic/workflows@2019-05-01' = {
  name: 'la-azportfolio-digest'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    state: 'Enabled'
    definition: loadJsonContent('workflow.json')
    parameters: {
      workspaceResourceId: { value: resourceId(workspaceResourceGroup, 'Microsoft.OperationalInsights/workspaces', workspaceName) }
      subscriptionId: { value: subscription().subscriptionId }
      sqlDbId: { value: sqlDb.id }
      actionGroupId: { value: actionGroup.id }
      storageAccount: { value: storageName }
      acsEndpoint: { value: 'https://${acs.properties.hostName}' }
      senderAddress: { value: 'DoNotReply@${emailDomain.properties.mailFromSenderDomain}' }
      repo: { value: repo }
      adxExpiry: { value: adxExpiry }
      budgetUsd: { value: budgetUsd }
      sqlFreeLimit: { value: sqlFreeLimit }
    }
  }
}

// ---------- Least-privilege roles for the Logic App identity (all read-only except two) ----------
var roleEmailOwner = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '09976791-48a7-449e-bb21-39d1a415f350')
var roleMonitoringReader = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '43d0d8ad-25c7-4714-9337-8ba259a9fe05')
var roleBlobReader = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
var roleBlobContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var roleQueueReader = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '19e7f393-937e-4f77-808e-94535e297925')

resource raSend 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acs.id, digest.id, roleEmailOwner)
  scope: acs
  properties: { roleDefinitionId: roleEmailOwner, principalId: digest.identity.principalId, principalType: 'ServicePrincipal' }
}
resource raMonitor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, digest.id, roleMonitoringReader)
  properties: { roleDefinitionId: roleMonitoringReader, principalId: digest.identity.principalId, principalType: 'ServicePrincipal' }
}
resource raQuarantine 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(quarantine.id, digest.id, roleBlobReader)
  scope: quarantine
  properties: { roleDefinitionId: roleBlobReader, principalId: digest.identity.principalId, principalType: 'ServicePrincipal' }
}
resource raDeadletter 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(deadletter.id, digest.id, roleBlobReader)
  scope: deadletter
  properties: { roleDefinitionId: roleBlobReader, principalId: digest.identity.principalId, principalType: 'ServicePrincipal' }
}
resource raPoison 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(poisonQueue.id, digest.id, roleQueueReader)
  scope: poisonQueue
  properties: { roleDefinitionId: roleQueueReader, principalId: digest.identity.principalId, principalType: 'ServicePrincipal' }
}
resource raHistory 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(opsdigest.id, digest.id, roleBlobContributor)
  scope: opsdigest
  properties: { roleDefinitionId: roleBlobContributor, principalId: digest.identity.principalId, principalType: 'ServicePrincipal' }
}

// ---------- Alerts: a failed Function request, and a failed digest run, email the action group ----------
resource components 'Microsoft.Insights/components@2020-02-02' existing = [for app in functionApps: { name: app }]

resource fnFailAlerts 'Microsoft.Insights/metricAlerts@2018-03-01' = [for (app, i) in functionApps: {
  name: 'alert-fn-failures-${replace(app, 'func-azportfolio-', '')}'
  location: 'global'
  properties: {
    description: 'A ${app} request failed in the last hour'
    severity: 2
    enabled: true
    scopes: [ components[i].id ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    autoMitigate: true
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [ { name: 'cond0', metricName: 'requests/failed', metricNamespace: 'microsoft.insights/components', operator: 'GreaterThan', threshold: 0, timeAggregation: 'Count', criterionType: 'StaticThresholdCriterion' } ]
    }
    actions: [ { actionGroupId: actionGroup.id } ]
  }
}]

resource digestFailAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-digest-failed'
  location: 'global'
  properties: {
    description: 'The weekly digest Logic App run failed'
    severity: 2
    enabled: true
    scopes: [ digest.id ]
    evaluationFrequency: 'PT1H'
    windowSize: 'PT6H'
    autoMitigate: true
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [ { name: 'cond0', metricName: 'RunsFailed', metricNamespace: 'Microsoft.Logic/workflows', operator: 'GreaterThan', threshold: 0, timeAggregation: 'Total', criterionType: 'StaticThresholdCriterion' } ]
    }
    actions: [ { actionGroupId: actionGroup.id } ]
  }
}

output digestPrincipalId string = digest.identity.principalId
