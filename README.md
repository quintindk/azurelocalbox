# azure-localbox

An [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
project that deploys Jumpstart **LocalBox** (nested 2-node Azure Local + Azure Arc
+ AKS Arc) into an **enterprise-vended, firewall-governed Virtual WAN spoke** in
South Africa North, registering the Azure Local instance in West Europe.

This is a **brownfield** adaptation of upstream
[`microsoft/azure_arc` → `azure_jumpstart_localbox`](https://github.com/microsoft/azure_arc/tree/main/azure_jumpstart_localbox).
Vendored sources and their pinned commits are recorded in
[`docs/vendor/SOURCES.md`](docs/vendor/SOURCES.md).

## Layout

```
azure.yaml                     # azd project (infra-only), points at infra/bicep/main.localbox
infra/
  bicep/
    main.localbox.bicep        # subscription-scoped wrapper (creates 2 RGs, BYO network)
    main.localbox.parameters.json
    network/network.byo.bicep  # references EXISTING LZ spoke subnet, creates nothing
    host/host.bicep            # patched: governed mode (no public IP / no in-spoke bastion)
    mgmt/, network/, host/     # vendored upstream modules (pinned)
    modules/rgRoleAssignment.bicep
  artifacts/PowerShell/        # vendored + patched in-VM automation
  hooks/                       # azd pre/postprovision
docs/vendor/localbox/          # pinned mirror of LocalBox docs (context)
```

## Key design decisions

| Area | Decision |
|---|---|
| Target subscription | `8d3c4bb2-fdf8-4bca-bb92-e387bd4766ea` (quintindekok-app) |
| Client VM + nodes RG | `rg-localbox-nodes-san-1` in **southafricanorth** |
| Azure Local registration RG | `rg-localbox-azlocal-we-1` in **westeurope** (SAN is not a supported Azure Local region) |
| Network | **BYO** — NIC placed in existing LZ spoke `vnet-az-test-wkl-san-1/snet-default` (`10.201.0.0/24`). We create **no** VNet/subnet/NSG/UDR/NAT/Bastion/public IP. |
| VM SKU | `Standard_E32s_v6` (available in SAN) |
| Management | Central LZ Azure Bastion (Standard, IP-based) over **RDP 3389** |
| Bastion NSG rule | `AzureBastionSubnet (10.202.0.0/26) -> 3389` added by the **LZ/connectivity team** on the spoke NSG (not by us) |
| Egress | Spoke forces `0.0.0.0/0 -> SAN Azure Firewall`; the LocalBox allowlist is already in place |
| Teardown | `azd down` destroys both our RGs; the LZ spoke is never touched |
| Foundry Local / GPU | Out of scope (all GPU SKUs are `NotAvailableForSubscription` in SAN) |

### Two-RG / registration behaviour (important)

Upstream LocalBox registers Arc nodes + the Azure Local cluster into a single RG,
and the Arc onboarding RG is **hard-coded to `$env:resourceGroup`** inside the
PSGallery module `Azure.Arc.Jumpstart.LocalBox` (`Set-AzLocalDeployPrereqs`).

Rather than fork that module, the wrapper passes the **westeurope registration RG**
as `-resourceGroup` to `Bootstrap.ps1`, so all in-VM Arc/cluster operations target
`rg-localbox-azlocal-we-1`. The client VM itself is created by Bicep in the SAN
nodes RG. Consequence: LocalBox **progress tags** are written to the westeurope RG
(cosmetic azd UX only); the deployment is unaffected. `New-LocalBoxCluster.ps1` is
patched to resolve the client VM across the subscription for tag propagation.

## Prerequisites

See [`docs/PREREQS.md`](docs/PREREQS.md). Summary:

1. `az login`; select the target subscription (PIM to Owner if required).
2. A service principal (client id `SPN_CLIENT_ID`) — already created for this
   project: `8bdd3df0-d1c0-470d-adf8-fa6056acabb1`. The deploying **user** (Owner
   on the subscription) assigns Owner on the two created RGs via the wrapper.
3. **Fork hosting for patched in-VM scripts.** Because `artifacts/PowerShell/*` are
   patched, the client VM must download **our** copies. Push the vendored+patched
   `azure_jumpstart_localbox/` tree to a fork of `azure_arc` and set:
   `azd env set JS_GITHUB_ACCOUNT <account>` / `JS_GITHUB_BRANCH <branch>`
   (wired into `templateBaseUrl`). *Until this is done the VM would pull unpatched
   upstream scripts.*
4. The LZ team confirms the spoke/subnet exists and adds the Bastion→3389 NSG rule.

## Deploy

```sh
azd env new localbox-san
azd env set SPN_CLIENT_ID 8bdd3df0-d1c0-470d-adf8-fa6056acabb1
azd env set JS_GITHUB_ACCOUNT quintindk
azd env set JS_GITHUB_BRANCH localbox-governed-san
# optional overrides: JS_LOCATION, JS_AZURELOCAL_LOCATION, JS_SPOKE_*, JS_VM_SIZE
azd provision
```

The client VM authenticates to Azure with its **system-assigned managed identity**
(`Connect-AzAccount -Identity`) — no SP client secret is consumed by the in-VM
automation. The SP (`SPN_CLIENT_ID`) is used only as the azd deployment principal;
the VM's managed identity is granted the roles it needs by `host.bicep`.

The in-VM automation continues for ~1–3 hours after `azd provision` returns.

## Teardown

```sh
azd down --purge
```

Removes `rg-localbox-nodes-san-1` and `rg-localbox-azlocal-we-1`. The LZ spoke
(`vnet-az-test-wkl-san-1`) and all connectivity resources are untouched.
