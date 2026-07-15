# Prerequisites & runbook

## 1. Identity / access
- `az login` and select the target subscription:
  ```sh
  az account set --subscription 8d3c4bb2-fdf8-4bca-bb92-e387bd4766ea
  ```
- Ensure you are **Owner** on the subscription (PIM activate if required). The
  deploying user assigns Owner on the two created RGs to the deployment SP via the
  wrapper's `rgRoleAssignment` modules.
- Service principal (already created): client id
  `8bdd3df0-d1c0-470d-adf8-fa6056acabb1`.
  ```sh
  azd env set SPN_CLIENT_ID 8bdd3df0-d1c0-470d-adf8-fa6056acabb1
  ```
  `preprovision` resolves its object id (`SPN_OBJECT_ID`) and the tenant id.

## 2. Resource providers
Registered idempotently by `infra/hooks/preprovision.sh`:
`Microsoft.HybridCompute, GuestConfiguration, Kubernetes, KubernetesConfiguration,
ExtendedLocation, AzureArcData, OperationsManagement, AzureStackHCI,
ResourceConnector, OperationalInsights, Compute`.

## 3. Microsoft.AzureStackHCI provider object id (`SPN_PROVIDER_ID`)
Resolved automatically by `preprovision` via:
```sh
az ad sp list --display-name "Microsoft.AzureStackHCI" --query "[0].id" -o tsv
```
If you lack directory read permission, ask a tenant admin for the id and:
```sh
azd env set SPN_PROVIDER_ID <object-id>
```

## 4. Fork hosting for patched in-VM scripts (REQUIRED)
`infra/artifacts/PowerShell/Bootstrap.ps1` and `New-LocalBoxCluster.ps1` are
**patched** for the governed vended-spoke / West Europe registration model. The
client VM downloads these via `templateBaseUrl`
(`https://raw.githubusercontent.com/<account>/azure_arc/<branch>/azure_jumpstart_localbox/`).

Push the vendored + patched tree to a fork of `microsoft/azure_arc` (place the
contents of `infra/` under `azure_jumpstart_localbox/`), then:
```sh
azd env set JS_GITHUB_ACCOUNT quintindk
azd env set JS_GITHUB_BRANCH  localbox-governed-san
```
> Fork in use: `quintindk/azure_arc`, branch `localbox-governed-san`
> (patched `Bootstrap.ps1` + `New-LocalBoxCluster.ps1` published there).
> If left as `microsoft/main`, the VM pulls **unpatched** upstream scripts and the
> two-RG / governed behaviour will NOT apply.

## 5. Landing-zone spoke (LZ/connectivity team)
- Confirm `vnet-az-test-wkl-san-1` / `snet-default` (`10.201.0.0/24`) exists in
  RG `rg-az-test-wkl-san-1` and is delegated for our use.
- LZ team adds the inbound NSG allow rule on the spoke subnet NSG:
  `source AzureBastionSubnet (10.202.0.0/26) -> TCP 3389`.
- Confirm the SAN Azure Firewall allowlist covers LocalBox bootstrap egress
  (GitHub, MCR, Azure Marketplace VHDs, Arc, AKS Arc). (Reported already in place.)

## 6. Capacity
`preprovision` verifies `Standard_E32s_v6` is not `NotAvailableForSubscription` in
`southafricanorth`. (Verified available at authoring time.)

## Deploy / teardown
```sh
azd env new localbox-san
azd env set SPN_CLIENT_ID 8bdd3df0-d1c0-470d-adf8-fa6056acabb1
azd env set JS_GITHUB_ACCOUNT <fork>
azd env set JS_GITHUB_BRANCH  <branch>
azd provision      # creates 2 RGs + client VM; in-VM automation runs ~1-3h
azd down --purge   # removes both RGs; LZ spoke untouched
```

## Post-deploy validation
- Client VM reachable via central Bastion (RDP 3389) at its private IP
  (`CLIENT_VM_PRIVATE_IP` output).
- Arc-connected machines (`AzLHOST1/2`) and the Azure Local cluster appear in
  `rg-localbox-azlocal-we-1` (westeurope).
- AKS Arc / custom location resources register in the same WE RG.
