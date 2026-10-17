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
          value: '${storage.properties.primaryEndpoints.blob}${funcB1PackageContainer}'
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
          value: '${storage.properties.primaryEndpoints.blob}${funcB2PackageContainer}'
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
  name: guid(storage.id, funcB1.id, roleBlobDataReader)
  scope: storage
  properties: { roleDefinitionId: roleBlobDataReader, principalId: funcB1.identity.principalId, principalType: 'ServicePrincipal' }
}
resource raFuncB1Lang 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(language.id, funcB1.id, roleCognitiveServicesUser)
  scope: language
  properties: { roleDefinitionId: roleCognitiveServicesUser, principalId: funcB1.identity.principalId, principalType: 'ServicePrincipal' }
}
resource raFuncB2Kv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, funcB2.id, roleKeyVaultSecretsUser)
  scope: keyVault
  properties: { roleDefinitionId: roleKeyVaultSecretsUser, principalId: funcB2.identity.principalId, principalType: 'ServicePrincipal' }
}
resource raGithubBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, githubIdentity.id, roleBlobDataContributor)
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
    description: 'Free SQL vCore-seconds consumed this month passed the threshold (production ${sqlFreeLimitThreshold} of 100,000)'
    severity: 2
    enabled: true
    scopes: [ sqlDb.id ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [ { name: 'free-limit', metricName: 'free_amount_consumed', metricNamespace: 'Microsoft.Sql/servers/databases', operator: 'GreaterThan', threshold: sqlFreeLimitThreshold, timeAggregation: 'Maximum', criterionType: 'StaticThresholdCriterion' } ]
    }
    actions: [ { actionGroupId: opsActionGroup.id } ]
  }
}

// ---------- Build #13: the data API — Function app on its own Flex plan, and API Management (Consumption) ----------
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
      deployment: { storage: { type: 'blobContainer', value: '${storage.properties.primaryEndpoints.blob}app-package-funcazportfoliob13-0322941', authentication: { type: 'StorageAccountConnectionString', storageAccountConnectionStringName: 'DEPLOYMENT_STORAGE_CONNECTION_STRING' } } }
      runtime: { name: 'python', version: '3.12' }
      scaleAndConcurrency: { instanceMemoryMB: 2048, maximumInstanceCount: 100 }
    }
  }
}

resource apim 'Microsoft.ApiManagement/service@2023-05-01-preview' = {
  name: apimName
  location: locationUs
  sku: { name: 'Consumption', capacity: 0 }
  properties: { publisherEmail: apimPublisherEmail, publisherName: apimPublisherName }
}

output staticSiteHint string = 'Static website on ${storage.name} is enabled on the data plane (az storage blob service-properties update --static-website), not in ARM.'
