#!/bin/bash
set -euo pipefail

# =============================================================================
# postprovision — governed vended-spoke LocalBox
#
# We create NO network objects, so there is no public IP and no NSG we own.
# Management is via the CENTRAL landing-zone Azure Bastion over RDP.
# =============================================================================

NODES_RG=$(azd env get-value NODES_RESOURCE_GROUP 2>/dev/null || echo "${JS_NODES_RG:-rg-localbox-nodes-san-1}")
AZLOCAL_RG=$(azd env get-value AZURE_LOCAL_RESOURCE_GROUP 2>/dev/null || echo "${JS_AZURELOCAL_RG:-rg-localbox-azlocal-we-1}")
PRIV_IP=$(azd env get-value CLIENT_VM_PRIVATE_IP 2>/dev/null || echo "")
RDP_PORT="${JS_RDP_PORT:-3389}"
ADMIN_USER="${JS_WINDOWS_ADMIN_USERNAME:-arcdemo}"

cat <<EOF

============================================================================
LocalBox provisioning submitted.

  Nodes / client VM RG   : ${NODES_RG}  (southafricanorth)
  Azure Local reg. RG    : ${AZLOCAL_RG}  (westeurope)
  Client VM private IP   : ${PRIV_IP:-<pending>}
  RDP port               : ${RDP_PORT}
  Windows admin user     : ${ADMIN_USER}

Connect via the CENTRAL landing-zone Azure Bastion (IP-based connection,
Standard SKU) to ${PRIV_IP:-<client VM private IP>}:${RDP_PORT}.

REMINDER: the AzureBastionSubnet (10.202.0.0/26) -> ${RDP_PORT} inbound allow
rule on the spoke subnet NSG is owned by the LZ/connectivity team. Confirm it
is in place before attempting to connect.

The in-VM automation (Bootstrap -> LogonScript -> New-LocalBoxCluster) continues
on the client VM for ~1-3 hours. It registers Arc nodes + the Azure Local cluster
into ${AZLOCAL_RG}. Track progress via the deployment tags / logs on the VM.
============================================================================
EOF
