# NODE2 Arc registration: confirmed authorisation failure

## Diagnosis

The read-only private inspection on 29 October 2026 confirmed:

- NODE1 bootstrap **Succeeded**. Its Azure Arc machine is **Connected** with
  system-assigned principal `9a1205c8-6ac3-4d02-ad6d-6166827c8d9d`. Do not register it again.
- NODE2 bootstrap failed at **ArcRegistration** after **ConnectivityValidation Succeeded**.
- NODE2's local agent log records **AuthorizationFailed** for
  **Microsoft.HybridCompute/machines/write** at **16:33:11–16:33:12 SAST on 28 October**.
- NODE2 has no Azure Arc machine resource. The error is resource-creation permission,
  not the private vault, guest startup, solution-update or connectivity check.
- Existing Owner access is active again at the time of this diagnosis. Its absence
  was independently observed after the failed bootstrap on 28 October. This is
  consistent with the reported PIM expiry. No PIM audit record was used to establish
  the exact expiry event.

The official [Connected Machine agent error reference](https://learn.microsoft.com/en-us/azure/azure-arc/servers/troubleshoot-agent-onboard#agent-exit-codes)
defines exit **42** as failure to create the Azure resource. The local log provides
the specific authorisation denial. A failed activity-log search alone did not
identify it. No raw agent log, bootstrap configuration, token or device code is
exported into the diagnostic receipt.

Evidence: `../deployment-2026-10-27/private-ssh-arc-registration-diagnosis-20261029.json`.

## One guarded recovery attempt

After the separate reviewed recovery package is installed, run in a real terminal:

```bash
python3 -B scripts/register-smal-node-console.py --node LB-NODE02 --retry-after-authorization-failure
```

- Ensure your existing PIM activation will remain active throughout registration.
  The launcher checks the previously used Owner assignment, but does not activate,
  extend or grant any role.
- Complete a **fresh** official device-code authentication with the approved account.
  Do not paste device codes into chat or files. No existing owner ARM token is exported.
- Only NODE2 is eligible. The launcher checks the diagnosed denial, current role
  assignment and absence of an Azure Arc machine. The host checks the current Failed
  registration/Succeeded connectivity state and local authorisation-denial evidence.
- The normal pinned module and selected solution version are reused. The retry uses
  the official initialization command, not a direct `azcmagent connect` workaround.
- The original console package, failed state and registration marker remain intact.
  A separate, create-only recovery marker/state prevents blind replay.
- Installing the recovery package does **not** invoke registration or authentication.

If the retry is interrupted or fails, do not delete either marker or repeat the
recovery command. Inspect:

```bash
python3 -B scripts/register-smal-node-console.py --node LB-NODE02 --inspect
```

After a console success, independently verify Azure identity, region, machine health
and actual bootstrap status before cluster deployment. Platform readiness remains false.

## Installed recovery package

At **08:58 SAST on 29 October**, the separate package was installed and hash-verified,
status **installed-not-invoked**. No authentication or registration was performed.
Receipt: `../deployment-2026-10-27/private-ssh-install-arc-recovery-console-20261029.json`.
The regression suite passed **180 tests** before installation. The remaining step
is the human-terminal command above with fresh device authentication.
