// main.bicep - the Azure learning portfolio as code (build #10).
// Scope: the existing resource group. Nothing here is deployed; `az deployment group what-if` compares this
// description with the live resources and prints the difference. Names only: no keys, no connection strings.
// App settings (which carry Key Vault references and connection strings) are deliberately not in this file.
targetScope = 'resourceGroup'

@description('Region for the Blob static site, Key Vault, AI Search and the deploy identity (student allowlist).')
param locationUs string = 'northcentralus'
@description('Region for SQL, Language, and the two Function apps (student allowlist).')
param locationEu string = 'germanywestcentral'
@description('Entra object id of the SQL server admin (the operator). Passed on the command line; never stored.')
param sqlAdminObjectId string
@description('Sign-in name of the SQL server admin, e.g. the operator UPN.')
param sqlAdminLogin string
param tenantId string = subscription().tenantId

param storageName string = 'stazportfoliob1'
param sqlServerName string = 'sql-azportfolio-b1eu'
param sqlDbName string = 'aid'
param keyVaultName string = 'kv-azportfolio-b2'
param languageName string = 'lang-azportfolio-b1'
param searchName string = 'srch-azportfolio-b1'
param githubIdentityName string = 'id-github-azportfolio'
param funcB1Name string = 'func-azportfolio-b1'
param funcB2Name string = 'func-azportfolio-b2'
param planB1Name string = 'ASP-rgazportfoliob1-845b'
param planB2Name string = 'ASP-rgazportfoliob1-4497'
param funcB1PackageContainer string = 'app-package-funcazportfoliob1-6177822'
param funcB2PackageContainer string = 'app-package-funcazportfoliob2-2154978'

// ---------- storage: raw data (build #1), function packages, and the $web static site (build #3) ----------
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: locationUs
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

// ---------- SQL: one logical server, one free-offer serverless database shared by every build ----------
resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: sqlServerName
  location: locationEu
  properties: {
    version: '12.0'
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
      principalType: 'User'
      login: sqlAdminLogin
      sid: sqlAdminObjectId
      tenantId: tenantId
    }
  }
}

resource sqlDb 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: sqlDbName
  location: locationEu
  sku: { name: 'GP_S_Gen5', tier: 'GeneralPurpose', family: 'Gen5', capacity: 2 }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 34359738368
    minCapacity: json('0.5')
    autoPauseDelay: 60
    useFreeLimit: true                       // the free offer: 100,000 vCore-seconds a month
    freeLimitExhaustionBehavior: 'AutoPause' // pause rather than bill when the free limit is spent
    zoneRedundant: false
    requestedBackupStorageRedundancy: 'Local'
  }
}

// ---------- Key Vault (build #2): RBAC, holds the two API keys by name; values never leave it ----------
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: locationUs
  properties: {
    tenantId: tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

// ---------- AI Language F0 (builds #1, #5) and AI Search free (build #1 stage 4) ----------
resource language 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: languageName
  location: locationEu
  kind: 'TextAnalytics'
  sku: { name: 'F0' }
  properties: { customSubDomainName: languageName, publicNetworkAccess: 'Enabled' }
}

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchName
  location: locationUs
  sku: { name: 'free' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    semanticSearch: 'free'
    disableLocalAuth: false
    authOptions: { aadOrApiKey: { aadAuthFailureMode: 'http401WithBearerChallenge' } }
    encryptionWithCmk: { enforcement: 'Unspecified' }
    networkRuleSet: { bypass: 'None' }
  }
}

// ---------- GitHub deploy identity (build #3): OIDC federated credential, no secret ----------
resource githubIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: githubIdentityName
  location: locationUs
}

// ---------- Two Flex Consumption Function apps (builds #1 and #2), system-assigned identities ----------
resource planB1 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: planB1Name
  location: locationEu
  kind: 'functionapp'
  sku: { name: 'FC1', tier: 'FlexConsumption' }
  properties: { reserved: true }
}

resource planB2 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: planB2Name
  location: locationEu
  kind: 'functionapp'
  sku: { name: 'FC1', tier: 'FlexConsumption' }
  properties: { reserved: true }
}

resource funcB1 'Microsoft.Web/sites@2024-04-01' = {
  name: funcB1Name
  location: locationEu
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: planB1.id
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: 'https://${storageName}.blob.${environment().suffixes.storage}/${funcB1PackageContainer}'
          authentication: { type: 'StorageAccountConnectionString', storageAccountConnectionStringName: 'DEPLOYMENT_STORAGE_CONNECTION_STRING' }
        }
      }
      runtime: { name: 'python', version: '3.12' }
      scaleAndConcurrency: { instanceMemoryMB: 2048, maximumInstanceCount: 100 }
    }
  }
}

resource funcB2 'Microsoft.Web/sites@2024-04-01' = {
  name: funcB2Name
  location: locationEu
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: planB2.id
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: 'https://${storageName}.blob.${environment().suffixes.storage}/${funcB2PackageContainer}'
          authentication: { type: 'StorageAccountConnectionString', storageAccountConnectionStringName: 'DEPLOYMENT_STORAGE_CONNECTION_STRING' }
        }
      }
      runtime: { name: 'python', version: '3.12' }
      scaleAndConcurrency: { instanceMemoryMB: 2048, maximumInstanceCount: 100 }
    }
  }
}

// ---------- Role assignments for the three service identities (the operator's own roles are not templated) ----------
var roleBlobDataReader = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
var roleBlobDataContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var roleCognitiveServicesUser = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
var roleKeyVaultSecretsUser = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')

resource raFuncB1Blob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: '0230c822-0657-485b-9261-05c7405d44b7' // live name (created by az cli, build #1); guid() can never reproduce it
  scope: storage
  properties: { roleDefinitionId: roleBlobDataReader, principalId: funcB1.identity.principalId, principalType: 'ServicePrincipal' }
}
resource raFuncB1Lang 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: '45033b0a-73f6-4f67-84b0-b3fac81ff9d0' // live name (build #1)
  scope: language
  properties: { roleDefinitionId: roleCognitiveServicesUser, principalId: funcB1.identity.principalId, principalType: 'ServicePrincipal' }
}
resource raFuncB2Kv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: 'ecf5d484-082d-4793-bb69-6e86697eed18' // live name (build #2)
  scope: keyVault
  properties: { roleDefinitionId: roleKeyVaultSecretsUser, principalId: funcB2.identity.principalId, principalType: 'ServicePrincipal' }
}
resource raGithubBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: 'b2f2fab3-795d-410c-b5e5-3a8b7b6395e3' // live name (build #3)
  scope: storage
  properties: { roleDefinitionId: roleBlobDataContributor, principalId: githubIdentity.properties.principalId, principalType: 'ServicePrincipal' }
}

// ---------- Build #12: the monitoring the Function wizard created, now described; plus the alert and its action group ----------
param workspaceResourceGroup string = 'DefaultResourceGroup-DEWC'
param workspaceName string = 'DefaultWorkspace-${subscription().subscriptionId}-DEWC'
param operatorEmail string   // passed on the command line; never stored
param sqlFreeLimitThreshold int = 80000

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: workspaceName
  scope: resourceGroup(workspaceResourceGroup)
}

resource aiB1 'Microsoft.Insights/components@2020-02-02' = {
  name: funcB1Name
  location: locationEu
  kind: 'web'
  properties: { Application_Type: 'web', WorkspaceResourceId: workspace.id, IngestionMode: 'LogAnalytics', RetentionInDays: 90 }
}

resource aiB2 'Microsoft.Insights/components@2020-02-02' = {
  name: funcB2Name
  location: locationEu
  kind: 'web'
  properties: { Application_Type: 'web', WorkspaceResourceId: workspace.id, IngestionMode: 'LogAnalytics', RetentionInDays: 90 }
}

resource opsActionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-azportfolio-ops'
  location: 'global'
  properties: {
    groupShortName: 'azpfops'
    enabled: true
    emailReceivers: [ { name: 'operator', emailAddress: operatorEmail, useCommonAlertSchema: false } ]
  }
}

resource sqlFreeLimitAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-sql-free-limit'
  location: 'global'
  properties: {
    description: 'Free SQL vCore-seconds consumed this month passed 80,000 of 100,000 (proved at 9,000 on 2026-10-16)'
    severity: 2
    enabled: true
    scopes: [ sqlDb.id ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [ { name: 'cond0', metricName: 'free_amount_consumed', operator: 'GreaterThan', threshold: sqlFreeLimitThreshold, timeAggregation: 'Maximum', criterionType: 'StaticThresholdCriterion' } ]
    }
    actions: [ { actionGroupId: opsActionGroup.id } ]
  }
}

// ---------- Build #13: the data API â€” Function app on its own Flex plan, and API Management (Consumption) ----------
param funcB13Name string = 'func-azportfolio-b13'
param apimName string = 'apim-azportfolio-b13'
param apimPublisherEmail string  // passed on the command line; never stored
param apimPublisherName string = 'Patrick Neil Bradley'

resource planB13 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'ASP-rgazportfoliob1-d595' // the CLI named the plan at create time
  location: locationEu
  kind: 'functionapp'
  sku: { name: 'FC1', tier: 'FlexConsumption' }
  properties: { reserved: true }
}

resource funcB13 'Microsoft.Web/sites@2024-04-01' = {
  name: funcB13Name
  location: locationEu
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: planB13.id
    functionAppConfig: {
      deployment: { storage: { type: 'blobContainer', value: 'https://${storageName}.blob.${environment().suffixes.storage}/app-package-funcazportfoliob13-0322941', authentication: { type: 'StorageAccountConnectionString', storageAccountConnectionStringName: 'DEPLOYMENT_STORAGE_CONNECTION_STRING' } } }
      runtime: { name: 'python', version: '3.12' }
      scaleAndConcurrency: { instanceMemoryMB: 2048, maximumInstanceCount: 100 }
    }
  }
}

resource apim 'Microsoft.ApiManagement/service@2023-05-01-preview' = {
  name: apimName
  location: locationUs
  sku: { name: 'Consumption', capacity: 0 }
  properties: {
    publisherEmail: apimPublisherEmail
    publisherName: apimPublisherName
    publicNetworkAccess: 'Enabled'
    legacyPortalStatus: 'Disabled'
    customProperties: {
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Protocols.Server.Http2': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Ssl30': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls10': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls11': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls10': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls11': 'False'
    }
  }
}

// ---------- Build #14: ingestion â€” validator Function app, Event Grid system topic + subscription, the loader container group ----------
param funcB14Name string = 'func-azportfolio-b14'
param loaderImage string = 'ghcr.io/patbradley18-netizen/azportfolio-loader:latest'
@description('A PUT on a container group redeploys it and can change its system identity (build #14). Off by default; set true only to recreate the loader on purpose.')
param deployLoader bool = false

resource planB14 'Microsoft.Web/serverfarms@2024-04-01' existing = { name: 'ASP-rgazportfoliob1-afb7' }

resource funcB14 'Microsoft.Web/sites@2024-04-01' = {
  name: funcB14Name
  location: locationEu
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: planB14.id
    functionAppConfig: {
      deployment: { storage: { type: 'blobContainer', value: 'https://${storageName}.blob.${environment().suffixes.storage}/app-package-funcazportfoliob14-7063208', authentication: { type: 'StorageAccountConnectionString', storageAccountConnectionStringName: 'DEPLOYMENT_STORAGE_CONNECTION_STRING' } } }
      runtime: { name: 'python', version: '3.12' }
      scaleAndConcurrency: { instanceMemoryMB: 2048, maximumInstanceCount: 100 }
    }
  }
}

resource inboxTopic 'Microsoft.EventGrid/systemTopics@2024-06-01-preview' = {
  name: 'egst-stazportfoliob1'
  location: locationUs
  identity: { type: 'SystemAssigned' }
  properties: { source: storage.id, topicType: 'Microsoft.Storage.StorageAccounts' }
}

resource inboxSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2024-06-01-preview' = {
  parent: inboxTopic
  name: 'evs-inbox-to-validator'
  properties: {
    destination: { endpointType: 'AzureFunction', properties: { resourceId: '${funcB14.id}/functions/validate_inbox_blob', maxEventsPerBatch: 1, preferredBatchSizeInKilobytes: 64 } }
    filter: { includedEventTypes: [ 'Microsoft.Storage.BlobCreated' ], subjectBeginsWith: '/blobServices/default/containers/inbox/' }
    retryPolicy: { maxDeliveryAttempts: 5, eventTimeToLiveInMinutes: 60 }
    deadLetterWithResourceIdentity: { identity: { type: 'SystemAssigned' }, deadLetterDestination: { endpointType: 'StorageBlob', properties: { resourceId: storage.id, blobContainerName: 'deadletter' } } }
  }
}

resource loader 'Microsoft.ContainerInstance/containerGroups@2023-05-01' = if (deployLoader) {
  name: 'aci-azportfolio-b14'
  location: locationUs
  identity: { type: 'SystemAssigned' }
  properties: {
    osType: 'Linux'
    restartPolicy: 'Never'
    provisioningTimeoutInSeconds: 1800
    containers: [ {
      name: 'aci-azportfolio-b14'
      properties: {
        image: loaderImage
        resources: { requests: { cpu: json('0.5'), memoryInGB: json('0.5') } }
        environmentVariables: [
          { name: 'STORAGE_ACCOUNT_URL', value: 'https://${storage.name}.blob.core.windows.net' }
          { name: 'QUEUE_ACCOUNT_URL', value: 'https://${storage.name}.queue.core.windows.net' }
          { name: 'SQL_SERVER_NAME', value: '${sqlServer.name}.database.windows.net' }
          { name: 'SQL_DATABASE_NAME', value: sqlDbName }
          { name: 'RUN_BY', value: 'aci-azportfolio-b14' }
          { name: 'MAX_DEQUEUE', value: '5' }
          { name: 'VISIBILITY_S', value: '30' } // 30 s: a failed message returns fast; 5 tries in ~3 min (code default 300)
        ]
      }
    } ]
  }
}

output staticSiteHint string = 'Static website on ${storage.name} is enabled on the data plane (az storage blob service-properties update --static-website), not in ARM.'

// ---------------- Build #15: two wars, matched years ----------------
// The Azure Data Explorer FREE cluster is not an ARM resource (it belongs to the signed-in account, not the subscription), so it is not
// templated: cluster `azportfolio` (https://kvc-1267rvs0jur9k7ncmj.southcentralus.kusto.windows.net), database `vets`, table `cps_raw`,
// principals: funcB13's identity as Ingestor + Viewer (`.add database vets ingestors ('aadapp=<clientId>;<tenantId>')`).
// The extract pipeline runs inside funcB13 (one app per Flex plan; plan creates were throttled on 2026-10-17).
param ipumsSecretName string = 'ipums-api-key'
param adxClusterUri string = 'https://kvc-1267rvs0jur9k7ncmj.southcentralus.kusto.windows.net'

module b15Settings 'appsettings-merge.bicep' = {
  name: 'b15-appsettings-merge'
  params: {
    siteName: funcB13.name
    existing: list(resourceId('Microsoft.Web/sites/config', funcB13Name, 'appsettings'), '2024-04-01').properties
    settings: {
      IPUMS_API_KEY: '@Microsoft.KeyVault(VaultName=${keyVault.name};SecretName=${ipumsSecretName})'
      ADX_CLUSTER_URI: adxClusterUri
      ADX_INGEST_URI: replace(adxClusterUri, 'https://', 'https://ingest-')
      ADX_DATABASE: 'vets'
      ADX_TABLE: 'cps_raw'
      STORAGE_ACCOUNT_URL: 'https://${storageName}.blob.${environment().suffixes.storage}/'
      IPUMS_CONTAINER: 'ipums'
    }
  }
}

resource ipumsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: '${storage.name}/default/ipums'
  properties: { publicAccess: 'None', defaultEncryptionScope: '$account-encryption-key', denyEncryptionScopeOverride: false }
}

resource b13KvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: '96f0c571-f3d9-4b9e-902c-ffb2968ce992' // live name (build #15)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
    principalId: funcB13.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------- Build #19: operations round two — the weekly digest ----------------
// Logic App + ACS Email + digest history container + failure alerts + the Logic App's RG-scope roles.
// Its two reads outside this group (Cost Management Reader on the subscription, Log Analytics Reader on the workspace)
// are in build-19-ops-digest/infra/sub-roles.bicep and are deployed by the operator: this pipeline's identity is RG-scoped by design.
module b19Digest '../../build-19-ops-digest/infra/digest.bicep' = {
  name: 'b19-digest'
}
