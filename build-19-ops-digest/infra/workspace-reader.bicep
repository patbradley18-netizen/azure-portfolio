param principalId string
param workspaceName string

var roleLogReader = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '73c42c96-874c-492b-b04d-ab87d138a893')

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = { name: workspaceName }

resource ra 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(workspace.id, principalId, roleLogReader)
  scope: workspace
  properties: { roleDefinitionId: roleLogReader, principalId: principalId, principalType: 'ServicePrincipal' }
}
