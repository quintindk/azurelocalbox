# Start LocalBox after the nightly shutdown

From `/home/quintin/play/azurelocalbox`:

```bash
python3 -B scripts/start-smal-localbox.py
```

## Prerequisites

- Existing Azure CLI sign-in with the approved account. Activate existing PIM
  access manually if needed. No role activation or grant is performed by this command.
- Connected `entlz-san-cert` VPN with actual `tun0` routes to the host and resolver.
  An Active profile alone is not sufficient. If the routes are stale, reconnect:

  ```bash
  nmcli connection down id entlz-san-cert
  nmcli connection up id entlz-san-cert
  ```

- Existing pinned SSH key and successful private Bastion setup receipts on this
  operator machine. This is not a portable first-time provisioning tool.
- Startup source must match committed HEAD and be pushed to the current branch.

## Behaviour

1. Checks source, private routing, resolver reachability and signed-in identity
   before requesting any start.
2. Starts only `LocalBox-Client` in `rg-localbox-nodes-san-1`. Already Running is
   a no-op. A Starting host is observed without another start request. Stopping,
   deallocating and unexpected states are refused.
3. Waits for host Running and Azure VM agent Ready, bounded by `--host-timeout`
   (default 900 seconds). This does not certify SSH availability.
4. Uses VPN → private Premium Bastion → pinned-key SSH to validate the exact four
   existing guest IDs, then starts the DC first, followed by NODE1, NODE2 and NODE3.
   Already Running guests are left alone. There is no DC service-readiness gate
   between guest starts.
5. Waits for healthy Hyper-V heartbeats from all four guests. Heartbeat means OS
   liveness, not working AD, DNS, PowerShell Direct, Arc or Azure Local readiness.

Safe to run again after a completed run. It does not reboot Running machines,
change automatic-start settings, bypass PIM, alter nightly shutdown automation,
register Arc nodes, delete registration markers or continue bootstrap.

Every invocation retains a distinct receipt under `docs/deployment-2026-10-29/`
and a separate private transport receipt under `docs/deployment-2026-10-27/`.
Failures, interruptions and uncertain timeouts are retained. The command does not
automatically replay remote operations. If it fails, inspect the named receipts
and actual VM state before running it again. Concurrent local invocations are refused.

For NODE2 bootstrap recovery, startup is followed by **inspection**, not registration:

```bash
python3 -B scripts/register-smal-node-console.py --node LB-NODE02 --inspect
```

## Verification, 29 October 2026

- Regression suite: 177 tests passed, including startup identity, routing, bounded
  waiting, uncertain-effect handling and no-op behaviour tests.
- Two consecutive live runs completed with host Running/agent Ready and all three
  guests Running with healthy heartbeats. Both requested **zero** host/guest starts.
- The combined command's stopped-host path was tested offline, not by deliberately
  shutting down the live environment. Earlier guest-start receipts independently
  record all three guests changing from Off to Running.
- Live receipts: `../deployment-2026-10-29/start-20261029-065230-91ec0efb.json`
  and `../deployment-2026-10-29/start-20261029-065252-f7c03032.json`.

### Real host deallocation and Premium conversion recovery

Later on 29 October, the existing disks were converted to Premium SSD while the
host was deallocated. The startup command requested a host start, then initially
refused a transient missing Azure PowerState during its observer loop. The original
receipt is retained. The observer now waits within its existing bound when a
previously accepted start briefly lacks PowerState. Missing state at the initial
decision point still refuses a start request.

After independent Running readback, a reconciled startup left the Running host
alone and started all three existing guests from Off to Running with healthy
heartbeats. V: and both Arc identities/bootstrap statuses were subsequently verified.
Arc services are configured for **delayed automatic start**. Early Stopped readings
are not a reason to register again or change their startup configuration.

Reconciled startup receipt:
`../deployment-2026-10-29/start-20261029-080708-7389325a.json`.
Final conversion/recovery evidence:
`../deployment-2026-10-29/premium-disk-conversion-reconciled-result.json`.

### Four-guest binding after NODE3 local completion

The current startup source includes NODE3's returned VM ID
`5b6eba15-fa82-4e12-9e45-5ffbcd48c8a9`. It is bound to the committed successful local
build/cleanup/login receipt, not inferred from its name. Historical three-guest
receipts above remain unchanged. The command now targets the DC and all three
Azure Local guests. NODE3's Arc authentication remains a separate human step.
