// RG-scoped role assignment helper.
@description('Principal (object) id to grant the role to')
param principalId string

@description('Role definition GUID (unqualified)')
param roleDefinitionGuid string

@description('Unique salt so multiple assignments of the same role to the same principal in one deployment get distinct names')
param nameSalt string = ''

resource assignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, principalId, roleDefinitionGuid, nameSalt)
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionGuid)
    principalType: 'ServicePrincipal'
  }
}
