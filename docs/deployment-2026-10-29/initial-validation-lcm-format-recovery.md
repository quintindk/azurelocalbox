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

References:

- [Azure Local portal: validation and deployment](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deploy-via-portal?view=azloc-2610#validate-and-deploy-the-system).
- [ARM deployment known licence-sync issue](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deployment-azure-resource-manager-template?view=azloc-2610#license-sync-issue).
- Pinned local REST source: `../deployment-2026-10-28/upstream-review/deployment-settings-schema-source.json`.
