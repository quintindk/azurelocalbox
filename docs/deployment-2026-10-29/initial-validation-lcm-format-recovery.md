# Initial validation failure: LCM username format

## Confirmed cause

The first service Validate ended **Failed/Error** at **14:25 SAST on 29 October**.
ARM error code: `UpdateDeploymentSettingsDataFailed`. The reported failing step is
`InvokeEnvironmentChecker` inside `Download content for deployment`.

The exact service error is:

> Domain user credential object cannot contain domain name as part of Username.

The encoder supplied `LOCALBOX\lboxdeploy` in the base64-encoded credential tuple.
This workflow requires **lboxdeploy**, with the domain supplied separately by the
deployment configuration. This was our encoder defect, not evidence that private
vault access, No Witness or policy must be weakened.

The service completed answer-file schema/value validation, including infrastructure
network, host network, physical-node and cluster-value checks, before credential
object initialization failed. These are configuration checks, **not** a successful
Environment Checker or platform acceptance. No Deploy was submitted.

Original failure records remain intact:

- `three-node-cluster-validate-receipt.json`.
- `three-node-validation-diagnostic.json` contains redacted excerpts/fingerprints,
  not raw credential/token material or signed URL queries.
- The original service/ARM deployment resource is not deleted or recreated.

## Exact permitted correction

`scripts/correct-smal-lcm-credential-format.py` is limited to the owned
`smal-localbox01-AzureStackLCMUserCredential` secret. Before writing it requires:

1. The live cluster is **ValidationFailed**, not DeploymentFailed, with the original
   inspected system-assigned principal. Settings are mode **Validate**, state Failed,
   validation Error, with no deployment status/steps or Deploy ARM request.
2. The current exception is the exact diagnosed username-format error.
3. Fresh node/storage/AD inspection still shows standalone healthy nodes, all twelve
   approved RAW devices, normal LCM account expiry and the approved OU.
4. Exactly one enabled original LCM secret version exists from our publication.
5. A fresh **LCM-only** RSA4096-OAEP-SHA256 envelope resolves the existing protected
   host DPAPI credential without returning clear values to the assistant.
6. In operator process memory, constant-time comparison proves that the current
   private-vault value matches that same password with the old qualified username.

Only then does one private HTTPS PUT create a new version encoding **lboxdeploy**
with the **same password**. The old version is retained. The local-admin secret,
AD account/password/policy, nodes, roles, cluster identity, storage and public-access
settings are not changed. The Vault data-plane token is used only locally for its
ordinary HTTPS request, never forwarded to the host. No owner ARM token is exported.

The normal three-node initial-publication path now also normalises this username
before publishing, with tests preserving the exact password/local-admin tuple.
The completed original publication receipt is not rewritten or replayed.

## Supported state distinction and retry boundary

The live cluster reports **ValidationFailed**. It does **not** report DeploymentFailed,
and reported deployment status is absent with no Deploy request. This matters:
the ARM guide warns against another Validate after **deployment** failure because
it can reset properties/licence synchronisation.

The portal guide documents correcting actionable validation errors and warns not
to select **Try again while validation tasks are running**. The current validation
is terminal Error, not running. The pinned 2025-09-15-preview REST schema exposes
**DeploymentSettings_CreateOrUpdate (PUT)** with mode Validate or Deploy. There is
no invented Resume API or unsupported mode in this recovery.

After the username-only fix is independently verified,
`scripts/retry-smal-initial-validation.py` permits **one** guarded initial-validation
attempt against the **same existing deploymentSettings resource**. It checks the
same settings-template hash and the same terminal non-deployment state immediately
before submission. Its what-if must show only that existing settings resource with
unchanged deployment mode, nodes and configuration. It does not reapply the cluster,
edges, roles, secrets, storage or licences. Original attempts/secret versions remain.

No automatic repeated retry or Deploy is permitted on failure. Deploy still requires
positive current reported service validation/step success, not ARM acceptance alone.

## Correction completed

At **14:49 SAST on 29 October 2026**, the guarded correction completed. Private
readback matched the unqualified username and unchanged host-bound password.
Exactly two enabled versions remain, including the original. The AD account,
local-admin secret and cluster were unchanged, and vault public access remained
Disabled. No Validate or Deploy was invoked by the correction.

Evidence: `lcm-credential-format-correction-receipt.json`, the encrypted LCM-only
transport receipt and fresh private node/storage/AD inspection. The initial failed
validation receipt remains unchanged. Service validation has not yet passed.

## Corrected validation still running after observer timeout

The single corrected Validate request was submitted with a **NoChange** what-if
for the existing settings. Its observer ended at **15:22 SAST**, retaining ARM
state Running. A subsequent read confirmed **ValidationInProgress**, not failure.
Remote management, connectivity, external AD, SBE health, hardware and network
configuration reported Success. Infrastructure network connection validation was
InProgress, with later checks pending and no reported exceptions.

`scripts/observe-smal-corrected-validation.py` observes only this existing request
and writes a separate observation receipt. It cannot submit Validate or Deploy.
The timeout receipt remains intact. Deploy stays blocked until both ARM and the
reported service validation positively succeed for the same template hash.

## Corrected validation failed at infrastructure networking

At **16:01 SAST on 29 October 2026**, the same corrected-validation ARM request
reported Failed and the service reported Error at **Azure Local Network Infra
Connection**. The first six checks remain Success. The cluster status remains
**ValidationFailed**, not DeploymentFailed. No Deploy has been submitted.

The redacted service diagnostic reports that temporary infrastructure-pool addresses,
including **10.64.0.20–10.64.0.25** on NODE1, could not reach gateway **10.64.0.1**
or be configured correctly on the test adapter. This identifies the failed test,
not yet its root cause. Gateway ICMP filtering, test-adapter configuration and
nested-switch forwarding require inspection before choosing a remediation.

The original corrected-validation timeout receipt and the final read-only observation
are retained separately. No validation retry is authorised by these diagnostics.
`scripts/inspect-smal-infra-network-failure.ps1` collects existing host/guest networking,
effective gateway ICMP rules and source-bound echo probes without changing networking
or disabling firewalls.

## Gateway echo diagnosis and proposed narrow correction

The private inspection at **16:05 SAST** verified all three nodes retain their
expected management addresses, default route through **10.64.0.1** and reachable
gateway MAC **00-15-5D-10-04-00**. Source-bound echo probes from **10.64.0.11–13**
all failed to the gateway and all succeeded to DC **10.64.0.10**. The host retains
the intended internal gateway address, LB-NAT and outer default route.

All effective host inbound IPv4 echo-request allow rules are disabled. The enabled
ICMP rule permits only destination-unreachable/fragmentation-needed, not echo.
This establishes an existing gateway echo failure independently of temporary test
adapter configuration. A scoped rule and successful follow-up probes are required
before claiming the infrastructure-pool test is repaired.

Proposed new **host-local** rule, not yet applied:

```powershell
New-NetFirewallRule -Name 'AzureLocalBox-InternalGateway-Echo-v4' `
  -DisplayName 'AzureLocalBox internal gateway echo' `
  -Direction Inbound -Action Allow -Enabled True -Profile Any `
  -Protocol ICMPv4 -IcmpType 8 `
  -InterfaceAlias 'vEthernet (LB-Fabric)' -LocalAddress '10.64.0.1' `
  -RemoteAddress '10.64.0.11-10.64.0.13','10.64.0.20-10.64.0.30'
```

This is a new inbound permission, so it awaits specific human approval. No existing
rule is enabled or widened. No outer-interface, Azure networking, NSG, shared
landing-zone, vault/storage access or firewall-profile change is proposed. The
three existing node IPs and the exact approved infrastructure pool are the only
sources. A guarded implementation must check ownership, refuse conflicting rules,
read back every scope filter and avoid duplicate creation. Validation must not be
retried until the correction and network probes pass and the same terminal
ValidationFailed/non-deployment distinction is independently reconfirmed.

Reference: [New-NetFirewallRule protocol, ICMP and address/interface filters](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule?view=windowsserver2025-ps).
Private evidence: `../deployment-2026-10-27/private-ssh-infra-network-failure-20261029.json`.

## Human-approved rule applied and verified

The owner selected **Approve scoped echo rule**, authorising exactly the proposed
rule and continuation after verified connectivity and validation gates. The approval
is retained in `gateway-echo-rule-approval.json`.

At **16:14 SAST**, the exact rule was created and independently inspected in both
PersistentStore and ActiveStore. All source ranges, destination, interface, protocol
and echo type matched the approval. Existing rule identities were preserved. No
firewall profile, outer/shared network or Azure resource was changed.

Fresh source-bound probes on **all three nodes now succeed to both 10.64.0.1 and
10.64.0.10**. This verifies the gateway echo correction for existing node addresses.
It does not claim that the service's temporary infrastructure-pool adapter test has
passed. That remains gated on a real service validation result.

Evidence: `gateway-echo-rule-receipt.json` and private before/after transport receipts.
The `--after-gateway-echo-fix` retry option requires this committed correction, the
specific human continuation approval, the exact terminal network error and unchanged
settings hash. It repeats fresh read-only rule/echo/node/storage/AD checks before
one existing-settings-only Validate request under a new retained attempt identity.
No secrets, roles, cluster, edges or licences are reapplied. There is no automatic
retry if this attempt fails, and Deploy still requires positive service success.

## Gateway validation retry blocked before submission by Azure authorisation

At **16:19 SAST**, fresh node/storage/AD inspection and effective-rule/echo checks
passed, but ARM rejected the what-if request for the approved deployer with
**AuthorizationFailed**, action **Microsoft.Resources/deployments/whatIf/action**.
The Azure CLI additionally raised `The content for this response was already consumed`,
obscuring the actual ARM error. A diagnostic-only what-if reproduced the denial.
No Validate PUT was submitted and no gateway-retry or Deploy ARM deployment exists.
The live cluster remains at the previous **ValidationFailed** state, settings mode
Validate, provisioning Failed, reported validation Error.

The gateway firewall correction remains applied and its three-node echo checks passed.
The failure is now an operator authorisation blocker, not evidence that the corrected
service network test has run or failed again. No privilege activation, new role grant,
login/session reset or resource replay was attempted. The human must restore the
existing authorised deployment access/session before continuation. Restored access
must be tested without bypassing what-if or granting broader permissions.

The original unsubmitted refusal and both original validation failures are retained.
Any later recovery must reconcile the original gateway-retry deployment identity and
retain the refused receipt, rather than deleting it or inventing a second service
attempt. It must repeat current non-deployment state, source/configuration, credential
metadata and local network/storage/AD checks before its single permitted submission.

Evidence:

- `three-node-cluster-validate-after-gateway-echo-receipt.json`.
- `gateway-validation-preview-reconciliation.json` (redacted error and fingerprint).
- `gateway-validation-unsubmitted-auth-reconciliation.json` (read-only absence/state proof).
- Fresh private input and pre-retry network observations.

## Access restored and exact unsubmitted attempt reconciliation

On **30 October 2026**, the human confirmed PIM roles activated and requested
continuation after startup/health checks. The host and all four guests are running.
Read-only checks verified current Arc, bootstrap, AD, exact RAW storage and private
network health. At **07:56 SAST**, an actual ARM what-if succeeded and showed only
**NoChange** for the same existing deploymentSettings resource. The gateway-retry
deployment identity is still absent and the cluster retains the exact terminal
network ValidationFailed state, with no deployment started.

`--resume-unsubmitted-gateway` requires the committed pre-preview refusal, exact
retained AuthorizationFailed reconciliation and unchanged settings-template hash.
It uses the **original gateway-retry ARM deployment identity**, not a new service
attempt. It retains the refused receipt and writes a separate reconciliation receipt.
Fresh node/storage/AD, effective rule/echo, secret-version metadata, authorisation
and terminal non-deployment state checks still run before one permitted submission.

The operator did not activate roles, broaden permissions or overwrite historical
receipts. Evidence: `gateway-validation-access-restored-20261030.json` and the
daily startup/health observations. Deploy remains gated on a positive reported
validation result, matching settings hash and current service state.

References:

- [Azure Local portal: validation and deployment](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deploy-via-portal?view=azloc-2610#validate-and-deploy-the-system).
- [ARM deployment known licence-sync issue](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deployment-azure-resource-manager-template?view=azloc-2610#license-sync-issue).
- Pinned local REST source: `../deployment-2026-10-28/upstream-review/deployment-settings-schema-source.json`.
