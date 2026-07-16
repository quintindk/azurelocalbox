#!/bin/bash
set -euo pipefail

# =============================================================================
# preprovision — governed vended-spoke LocalBox
#
# Assumes:
#   * You are logged in to az and the target subscription is selected.
#   * The service principal already exists; its client id is in SPN_CLIENT_ID.
#   * The LZ spoke (vnet-az-test-wkl-san-1/snet-default) already exists.
# =============================================================================

echo "==> Registering required resource providers (idempotent)..."
for rp in \
  Microsoft.HybridCompute \
  Microsoft.GuestConfiguration \
  Microsoft.Kubernetes \
  Microsoft.KubernetesConfiguration \
  Microsoft.ExtendedLocation \
  Microsoft.AzureArcData \
  Microsoft.OperationsManagement \
  Microsoft.AzureStackHCI \
  Microsoft.ResourceConnector \
  Microsoft.OperationalInsights \
  Microsoft.HybridConnectivity \
  Microsoft.HybridContainerService \
  Microsoft.Attestation \
  Microsoft.Compute ; do
  az provider register --namespace "$rp" >/dev/null 2>&1 || true
done
echo "    Providers registration requested."

# ---- Client VM SKU availability in the client VM region (not a hub region) ----
JS_LOCATION="${JS_LOCATION:-southafricanorth}"
JS_VM_SIZE="${JS_VM_SIZE:-Standard_E32s_v6}"
echo "==> Checking client VM SKU $JS_VM_SIZE availability in $JS_LOCATION..."
restriction=$(az rest --method get \
  --url "https://management.azure.com/subscriptions/${AZURE_SUBSCRIPTION_ID}/providers/Microsoft.Compute/skus?api-version=2021-07-01&\$filter=location eq '${JS_LOCATION}'" \
  --query "value[?name=='${JS_VM_SIZE}'].restrictions[0].reasonCode | [0]" -o tsv 2>/dev/null || echo "")
if [ "$restriction" = "NotAvailableForSubscription" ]; then
  echo "ERROR: $JS_VM_SIZE is restricted (NotAvailableForSubscription) in $JS_LOCATION. Aborting." >&2
  exit 1
fi
echo "    $JS_VM_SIZE is available in $JS_LOCATION."

# ---- Windows admin username ----
JS_WINDOWS_ADMIN_USERNAME="${JS_WINDOWS_ADMIN_USERNAME:-arcdemo}"
read -r -p "Windows admin username [$JS_WINDOWS_ADMIN_USERNAME]: " promptOutput || true
[ -n "${promptOutput:-}" ] && JS_WINDOWS_ADMIN_USERNAME="$promptOutput"
azd env set JS_WINDOWS_ADMIN_USERNAME "$JS_WINDOWS_ADMIN_USERNAME"

# ---- Windows admin password (secure; stored in azd env) ----
if [ -z "${JS_WINDOWS_ADMIN_PASSWORD:-}" ]; then
  while true; do
    read -r -s -p "Windows admin password (12-123 chars, complexity): " pw1; echo
    read -r -s -p "Confirm password: " pw2; echo
    if [ "$pw1" = "$pw2" ] && [ "${#pw1}" -ge 12 ]; then
      azd env set JS_WINDOWS_ADMIN_PASSWORD "$pw1"
      break
    fi
    echo "Passwords did not match or too short; try again."
  done
fi

# ---- Microsoft.AzureStackHCI resource provider object id ----
if [ -z "${SPN_PROVIDER_ID:-}" ]; then
  echo "==> Resolving Microsoft.AzureStackHCI provider service principal object id..."
  spnProviderId=$(az ad sp list --display-name "Microsoft.AzureStackHCI" --query "[0].id" -o tsv 2>/dev/null || echo "")
  if [ -z "$spnProviderId" ]; then
    echo "ERROR: Could not resolve Microsoft.AzureStackHCI provider object id." >&2
    echo "Ask a tenant admin to run: az ad sp list --display-name 'Microsoft.AzureStackHCI' --query [0].id -o tsv" >&2
    echo "then: azd env set SPN_PROVIDER_ID <id>" >&2
    exit 1
  fi
  azd env set SPN_PROVIDER_ID "$spnProviderId"
fi

# ---- Deployment service principal (already created; client id provided) ----
if [ -z "${SPN_CLIENT_ID:-}" ]; then
  echo "ERROR: SPN_CLIENT_ID is not set. This project expects an existing service principal." >&2
  echo "Set it with: azd env set SPN_CLIENT_ID <appId>" >&2
  exit 1
fi
# Resolve the SP object (principal) id used for RG Owner role assignments.
if [ -z "${SPN_OBJECT_ID:-}" ]; then
  spnObjectId=$(az ad sp show --id "$SPN_CLIENT_ID" --query id -o tsv 2>/dev/null || echo "")
  if [ -z "$spnObjectId" ]; then
    echo "ERROR: Could not resolve object id for SP $SPN_CLIENT_ID." >&2
    exit 1
  fi
  azd env set SPN_OBJECT_ID "$spnObjectId"
fi
# Tenant id
if [ -z "${SPN_TENANT_ID:-}" ]; then
  azd env set SPN_TENANT_ID "$(az account show --query tenantId -o tsv)"
fi

echo "==> preprovision complete."
