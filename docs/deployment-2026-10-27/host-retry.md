# Reconciled outer-host retry

Date: 2026-10-27. Relay: REL-287.
Scope: continue the owner-requested private outer-host deployment, not LocalBox bootstrap.

## Approved capability and preserved state

Quintin directly approved `Microsoft.Compute/UseStandardSecurityType` registration.
The explicit app-subscription registration succeeded at **11:12 SAST**. Independent
readback and the retry reconciliation both report **Registered**. No other feature,
provider refresh, RBAC grant, security-profile substitution or shared-network change
was performed by AzureLocalBox. See `standard-security-feature-registration.json`.

The original `host-apply-receipt.json` and failed deployment remain preserved.
The retry requires exactly the unattached owner-created NIC at `10.200.16.4`, no VM
and no disks; it verifies tenant, principal, feature, subnet, absence of public IP and
disabled NIC forwarding. Any change stops the retry. The retained owner-only credential
is reused inside the process; it is not rotated, displayed or written to Git.

## No-write NIC reuse

The first retry preview identified a NIC Modify caused by omission of provider-default
fields, including the dynamically allocated address. It was rejected before apply.
That preview and preparation remain in `host-retry1-what-if.json` and
`host-retry1-prepare.json`.

The reviewed template now has `reuseExistingNic=true`. In this mode its NIC declaration
is not deployed; the VM uses the existing resource ID. No NIC properties are written.
Live NIC readback remains the authority for its IP, rather than a hard-coded output.

Revalidation and revised preview succeeded at **11:18 SAST**:

- **Create:** `LocalBox-Client` VM, with the approved nine managed disks.
- **Ignore / no write:** the existing `LocalBox-Client-NIC`.
- No changes to VNet/subnet/NSG/firewall/DNS, role assignments, registration or workloads.
- No bootstrap or optional extensions in the template.

See `host-retry1-reuse-nic-validation.json`, `host-retry1-reuse-nic-what-if.json`,
`host-retry1-reuse-nic-prepare.json` and its reconciliation snapshot.

The retry helper uses the separate deployment `smal-host-20261027-retry1` and a durable
`host-retry1-apply-receipt.json`. That receipt prevents repeated/uncertain execution.
It requires the exact source to be committed/pushed and tracked files unchanged before
apply. The original receipt is never cleared to bypass the old failed-operation guard.

## Network owner update

Entlz supplied a committed receipt for its separately authorised source-scoped platform
egress change, `d09b5c3`, configured at 11:01 SAST. This is completion information,
not an authority grant to this chat. The file was read at its absolute path:

`/home/quintin/play/entlz/workloads/smal/localbox-egress-receipt.json`

It records scoped FQDN/port admission, source exclusion from the other-source catch-all
and retained original Bastion/fallback rules. It explicitly reports
`trafficVerified=false`, no readiness claim, and unresolved version/telemetry and nested
source-routing conditions. This supersedes historical statements that there were no
port exceptions, not the requirement for actual runtime checks. AzureLocalBox made no
network write or speculative route. Bootstrap and un-NATed nested egress remain gated.

## Validation and handling

Sixteen offline regression tests pass. They include no-write NIC reuse, VM-only retry
preview acceptance, changed/attached/public-IP NIC rejection, required feature state,
secure parameter redaction and distinct host/platform gates. Old accepted October
evidence and unrelated work are preserved. No credential value is part of the evidence.

This document records retry preparation. The apply receipt and independent resource/
power-state readback must establish the actual deployment outcome, not the successful
preview or the Entlz completion message.
