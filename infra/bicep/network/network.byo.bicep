// BYO (bring-your-own) network module for governed vended-VNet deployments.
//
// Unlike the stock network.bicep, this module CREATES NOTHING. It only
// resolves an EXISTING landing-zone spoke subnet and returns its resource ID,
// so `azd down` never touches LZ-owned network objects (VNet / subnet / NSG /
// UDR / NAT / Bastion / public IP are all owned by the connectivity team).
//
// The client VM NIC (created in host.bicep) attaches to this subnet even though
// the subnet lives in a different resource group / is owned by the LZ.

@description('Name of the EXISTING landing-zone spoke virtual network')
param virtualNetworkName string

@description('Name of the EXISTING subnet within the spoke VNet to place the client VM NIC into')
param subnetName string

@description('Resource group that contains the EXISTING spoke VNet (LZ-owned). Defaults to the current resource group when the VNet is co-located.')
param virtualNetworkResourceGroup string = resourceGroup().name

@description('Subscription that contains the EXISTING spoke VNet (LZ-owned). Defaults to the current subscription.')
param virtualNetworkSubscriptionId string = subscription().subscriptionId

resource existingVnet 'Microsoft.Network/virtualNetworks@2024-07-01' existing = {
  name: virtualNetworkName
  scope: resourceGroup(virtualNetworkSubscriptionId, virtualNetworkResourceGroup)
}

resource existingSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-07-01' existing = {
  name: subnetName
  parent: existingVnet
}

output vnetId string = existingVnet.id
output subnetId string = existingSubnet.id
