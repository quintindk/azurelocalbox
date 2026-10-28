# LocalBox bootstrap continuation, 28 October 2026

## Latest verified result, 10:14 SAST

- The approved storage job is **storage-complete**, task result `0`. Independent
  readback at 09:49 SAST found Healthy NTFS V: at **2,181,825,495,040 bytes**.
  The worker verified the C: boot identity and partition unchanged.
- Original launch failure, timeout, marker, worker and state backups remain retained.
  The corrected resume used exact-byte-length, SHA-256-verified stdin. Only the two
  exactly identified orphan transport processes were stopped. No storage replay ran.
- Entlz applied the approved `*.microsoft.com` HTTPS rule for `10.200.16.0/24`.
  Host HEAD at 09:51 SAST returned **200**, exact expected **8,152,356,864 bytes**
  and ETag for the approved Evaluation ISO. This proves that specific host request,
  not a download, nested egress or platform readiness.
- No nested VM, domain, registration, resource bridge, custom location, AKS or
  workload deployment is established by these receipts.
- Relay's main task reads `done`, revision `13`, updated `2026-10-28T05:55:03.338Z`.
  Complete comment traversal contains no closure explanation. This conflicts with
  actual readiness. No cause is inferred and no task was reopened or redispatched.
- The cancelled cron remains off. The storage job has no recurring trigger.
- The approved Evaluation-media one-shot task is **media-downloaded**, task result
  `0`, independently read at 09:56 SAST. Final length is **8,152,356,864 bytes**,
  no partial file remains, and the worker's measured SHA-256 is
  `7B052573BA7894C9924E3E87BA732CCD354D18CB75A883EFA9B900EA125BFD51`.
  No publisher SHA-256 was supplied. The ISO remains unmounted/unexecuted at
  `C:\ProgramData\AzureLocalBox\Bootstrap\eval-media-20261028-01\WindowsServer2025Evaluation.26100.32230.x64.en-us.iso`.
- One observation timed out before SSH authentication. Its failure receipt remains
  intact. Independent Azure readback showed Running/agent Ready and the VPN route
  remained on tun0. A new read-only observation succeeded. The download task was
  neither restarted nor reinstalled.
- Owner subsequently approved the exact local guest proposal and its explicit
  DPAPI/temporary-answer-file secret boundary. Consent is bound to the proposal
  SHA-256 in `deployment-decisions.json`. Do not request the same consent again.
- Local network apply succeeded at **10:13:53 SAST**, independently read at
  **10:14:21 SAST**: Internal switch `LB-Fabric`, ID
  `995f5a7a-d229-4ca0-bb2a-9b34529c6934`, gateway `10.64.0.1/24`, exactly one
  WinNAT object `LB-NAT`, selector `10.64.0.0/20`. Outer `10.200.16.4`, default
  gateway `10.200.16.1` and DNS `10.204.0.4` are unchanged. No external switch,
  Azure network write or NIC-forwarding change. Guest traffic remains untested.
- Initial synchronous input inspection timed out without attached media or DISM
  processes. Only its exact two orphan PowerShell processes were stopped after
  identity/creation-time checks. Separate durable one-shot inspection
  `LocalBox-GuestInputs-20261028-02` now records phases independently of SSH.
  At 10:14 SAST it was still checking the Azure Local ISO hash. Do not equate this
  running phase with image inspection success or rerun it without reconciliation.

Current receipts:

- `../deployment-2026-10-27/private-ssh-storage-worker-recovery-framed-20261028.json`
- `../deployment-2026-10-27/private-ssh-storage-job-progress-20261028-02.json`
- `../deployment-2026-10-27/private-ssh-eval-media-access-post-wildcard-20261028.json`
- `../deployment-2026-10-27/private-ssh-eval-media-job-start-20261028.json`
- `../deployment-2026-10-27/private-ssh-eval-media-job-final-observation-20261028.json`
- `../deployment-2026-10-27/private-ssh-local-network-apply-20261028.json`
- `../deployment-2026-10-27/private-ssh-local-network-readback-20261028.json`

## Verified starting state and recovery

The following starting-state inventory predates the completed storage job.

- Relay has no active execution/obligations in this chat. The old ten-minute cron
  is cancelled at revision 2 and is not being restarted.
- The deployment host's VPN profile claimed Active but had no resolver tunnel route.
  One reconnect of the existing `entlz-san-cert` profile restored actual `tun0`
  routing and TCP 53 reachability to `10.204.0.4`. No profile/key changes occurred.
- The Azure VM was deallocated overnight by principal
  `da847d8c-ee71-44de-b462-6775e7d649a7`, successful at `2026-10-27T22:48:16Z`.
  That caller's governance/operating purpose was not inferred from its ID.
- The first start attempt was denied with `AuthorizationFailed`. Original failure
  and independent deallocated readback were retained. Quintin then reported
  **Approved access restored**. One reconciled start succeeded. No role activation,
  role assignment or shutdown-control change was made by the agent.
- Private Bastion key-only administration was freshly verified after startup.
  VMMS and Defender are active, no nested VM/switch/NAT or LocalBox task exists at
  that observation, and the 2610 ISO remains unattached.

Receipts: `host-start-action.json`, `host-start-after-access-restored.json`, and
`../deployment-2026-10-27/private-ssh-nvme-inventory-started-20261028.json`.

## Exact NVMe disk identities

The host uses NVMe, not SCSI. The
[official remote NVMe FAQ](https://learn.microsoft.com/en-us/azure/virtual-machines/enable-nvme-remote-faqs)
documents Windows `SCSILogicalUnit = Azure LUN + 1` for the observed
`Virtual_Disk NVMe Premium` model. The captured single-controller profile has data
namespaces 1–8 corresponding to Azure LUNs 0–7.

`map-smal-nvme-disks.py` verifies that correlation and exact agreement between
Storage/Win32/PhysicalDisk unique IDs, serials, sizes and poolability. It rejects
boot/system/non-RAW/offline/read-only disks, ambiguous identities and other controller
profiles. Windows disk numbers are recorded for diagnostics, never the selection key.
The resulting eight identities are in `nvme-data-disk-map.json`.

## Explicit local decisions

Quintin selected **Simple 2 TiB (Recommended)**, approved the bounded Entlz network
review delegation and accepted current Windows Server 2025 Evaluation media/terms
for management/domain infrastructure. See `deployment-decisions.json`. These
decisions do not approve new cloud-role grants, cloud costs or unreviewed shared
network changes. The OS disk is excluded from storage formatting.

## Real asynchronous storage phase

The committed worker/installer/readback scripts implement only the approved storage
phase. They do not claim to implement or complete the remaining cluster bootstrap.

- One Windows task: `LocalBox-Storage-20261028-01`, SYSTEM, no stored password,
  no recurring or logon/startup trigger, no automatic retry, IgnoreNew overlap policy.
- State: `C:\ProgramData\AzureLocalBox\Bootstrap\storage-20261028-01\state.json`.
- Independent .NET timer heartbeat: `heartbeat.json`, every 15 seconds while executing.
- Sanitised phase events: `events.jsonl`. No transcript rewriting or secret logging.
- Installer checks source/manifest hashes, preserves existing tasks/directories and
  refuses policy bypass. Administrator/SYSTEM ACLs protect the owned run directory.
- Worker checks actual Azure VM resource ID through metadata, exact private IP,
  Defender, all eight NVMe/physical identities and current RAW/poolable state before
  any mutation. It excludes the C: boot disk and requires V: and owned pool/VD names
  to be absent.
- Only those eight physical disks are supplied to the new Simple pool. The worker
  creates its own fixed virtual disk and initialises/formats only that returned disk,
  never a wildcard disk set. Final checks bind pool membership, V: NTFS health/size
  and unchanged C: partition/boot identity.
- Every mutating phase has a durable pre-operation checkpoint. A started marker and
  mutex fence repeated execution. A failure is **inspect-before-resume**, not an
  invitation to delete the marker or replay formatting.

The installer ACK is not storage success. Use the actual worker/readback receipt to
establish the result:

```bash
python3 -B scripts/smal-private-powershell.py \
  --script scripts/read-smal-storage-job.ps1 \
  --receipt your-new-storage-observation
```

No nested VM creation, network application, ISO mounting/execution, domain secret
generation or cloud registration belongs to this storage-only job.

## Network and media review

The separately assigned read-only Entlz review completed. Its report/evidence hashes
match the returned result. It found no overlap in the inspected estate, but explicitly
retained candidate/unreserved status and required concrete routing/NAT/DNS corrections.
See `network-review-receipt.json` and the linked report. No permission to apply the
old draft is inferred from that review.

The official Evaluation Center currently links a January 2026 Windows Server 2025 ISO
and an older 2024 VHDX. Prefer the newer ISO, not the old VHDX. The evaluation is 180
days and requires online activation in the first 10 days. Metadata is retained in
`windows-server-eval-metadata.json`; no publisher SHA-256 was supplied by that page.
Do not mislabel a measured/first-seen hash as a publisher checksum.

`start-smal-eval-media-job.ps1` and `smal-eval-media-worker.ps1` implement the approved
**download-only** continuation. The installer refuses an existing job, requires exact
committed/pushed source and explicit recorded media/terms approval, deploys to an
Administrator/SYSTEM-only directory, and starts one SYSTEM task with no trigger/retry.
The worker checks host/IMDS identity, Defender, free space and exact manifest hash,
uses normal TLS and `If-Match`, rejects redirects and ETag/length drift, and retains
partial bytes and the original marker on failure. State records progress every 15
seconds while bytes arrive. A blocked read can make this older, so also inspect task
state and file length rather than treating it as an independent heartbeat.

On success the file stays in the owned job directory, **unmounted and unexecuted**.
Its measured SHA-256 is provenance, not publisher authentication. No guest answer
file, credential, domain, VM or cloud registration is created by this task.

```bash
python3 -B scripts/smal-private-powershell.py \
  --script scripts/read-smal-eval-media-job.ps1 \
  --receipt your-new-eval-media-observation
```

The link-extraction tool unexpectedly traversed beyond the requested page despite the
budget cap. That path was stopped, its reported credits retained in
`spider-links-budget-incident.json`, and the user informed. A subsequent single-page
HTML read resolved the exact links without another crawl. No user secrets were sent.

The remaining local guest/network/credential implementation and exact registration
scope/cost/export decisions still need completion before a full deployment claim.

The [owner-approved local guest proposal](local-guest-apply-proposal.md) defines the
proposed two-node/DC resource budget, initial single-switch management topology,
one NAT selector, domain DNS and temporary-secret/DPAPI boundary. Its original
proposed wording is retained byte-for-byte to preserve the consent hash. The
local network is now applied. Guest/domain orchestration is still unfinished.
Future AKS/pod/service networks remain unused.
