# LocalBox bootstrap continuation, 28 October 2026

## Verified starting state and recovery

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

The link-extraction tool unexpectedly traversed beyond the requested page despite the
budget cap. That path was stopped, its reported credits retained in
`spider-links-budget-incident.json`, and the user informed. A subsequent single-page
HTML read resolved the exact links without another crawl. No user secrets were sent.

The remaining local guest/network/credential implementation and exact registration
scope/cost/export decisions still need completion before a full deployment claim.
