// Build #19: the two reads the weekly digest needs outside rg-azportfolio-b1.
// Subscription scope, so it is deployed once by the operator (az deployment sub create), not by the
// GitHub pipeline, whose identity is deliberately limited to rg-azportfolio-b1.
targetScope = 'subscription'

param digestPrincipalId string
param workspaceResourceGroup string = 'DefaultResourceGroup-DEWC'
param workspaceName string = 'DefaultWorkspace-${subscription().subscriptionId}-DEWC'

var roleCostReader = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '72fafb9e-0641-4937-9268-a91bfd8191a3')

// Month-to-date cost for the $10 line
resource raCost 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().id, digestPrincipalId, roleCostReader)
  properties: { roleDefinitionId: roleCostReader, principalId: digestPrincipalId, principalType: 'ServicePrincipal' }
}

// Function runs and failures from the Log Analytics workspace
module wsReader 'workspace-reader.bicep' = {
  name: 'b19-workspace-reader'
  scope: resourceGroup(workspaceResourceGroup)
  params: { principalId: digestPrincipalId, workspaceName: workspaceName }
}
