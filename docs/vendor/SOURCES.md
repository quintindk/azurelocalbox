# Vendored documentation sources

This folder contains a **pinned, read-only mirror** of upstream Jumpstart LocalBox
documentation, vendored for local context. Do not hand-edit vendored files; re-run
the fetch against a new pinned commit to update.

## LocalBox docs — `docs/vendor/localbox/`

| Field | Value |
|---|---|
| Source repo | `Azure/arc_jumpstart_docs` |
| Path | `docs/azure_jumpstart_localbox/` |
| Pinned commit | `71a945c619f78acb441c6470d76a9b58347169fe` |
| Retrieved (UTC) | 2026-07-15 |
| Method | GitHub raw at pinned SHA (not the jumpstart.azure.com SPA) |

Pages mirrored (`_index.md` + images): `getting_started`, `deployment_az`,
`cloud_deployment`, `using_localbox`, `troubleshooting`, `faq`, `manual_deployment`,
plus sub-guides `AKS`, `RB`, `SQLMI`, `WAC`.

Rendered site equivalent: <https://jumpstart.azure.com/azure_jumpstart_localbox/getting_started>

## Deployment code (referenced, vendored under `infra/` when scaffolded)

| Field | Value |
|---|---|
| Source repo | `microsoft/azure_arc` |
| Path | `azure_jumpstart_localbox/` (bicep + `artifacts/PowerShell`) |
| Pinned commit | `027b9554b2534af190271bd7443d8556da745d3e` |
| Retrieved (UTC) | 2026-07-15 |

---

## LZ delta — how our deployment deviates from stock LocalBox

Our deployment is a **brownfield** install into an enterprise-vended, firewall-governed
Virtual WAN spoke. Key deviations from the upstream single-subscription/single-RG design:

1. **Bring-your-own network.** We deploy the client VM NIC into the **existing**
   LZ spoke subnet `vnet-az-test-wkl-san-1/snet-default` (`10.201.0.0/24`). Our Bicep
   creates **no** VNet, subnet, NAT gateway, Bastion, NSG-on-subnet, UDR, or public IP —
   so `azd down` never touches LZ-owned network objects.

2. **No public IP on the VM.** `host.bicep` is patched with a "governed" mode that
   attaches the NIC to the existing subnet with **no public IP and no in-spoke Bastion**.
   Management is via the **central** Azure Bastion (`10.202.0.0/26`) over **RDP 3389**.
   The `AzureBastionSubnet -> 3389` inbound NSG rule is owned/added by the **LZ team**
   on the spoke subnet NSG, not by us.

3. **Two resource groups (we own both, created by our wrapper):**
   - `rg-localbox-nodes-san-1` (southafricanorth) — host VM, NIC, disks, LAW, storage, KV.
   - `rg-localbox-azlocal-we-1` (westeurope) — Arc-connected machines + Azure Local
     cluster registration. Requires patching the in-VM automation
     (`Bootstrap.ps1` / `Generate-ARM-Template.ps1` / logon script) to target a separate
     `azureLocalResourceGroup`; stock LocalBox registers everything into one RG.

4. **Region split.** Client VM in `southafricanorth` (SAN is **not** a supported Azure
   Local region); `azureLocalInstanceLocation = westeurope` for the Arc/Local resources.

5. **Egress.** The spoke forces `0.0.0.0/0 -> SAN Azure Firewall`; the firewall allowlist
   for LocalBox bootstrap FQDNs is already in place (treated as unrestricted egress).

6. **Patched in-VM scripts hosting.** Because we patch `artifacts/PowerShell/*`, the VM
   must download our patched copies. `templateBaseUrl` is pointed at our fork/branch of
   `azure_arc` (via `githubAccount`/`githubBranch`), not `microsoft/main`.

7. **Out of scope.** Foundry Local and all GPU SKUs are deferred (all GPU SKUs are
   `NotAvailableForSubscription` in SAN, and LocalBox cannot pass a GPU into its nested
   Azure Local guests).
