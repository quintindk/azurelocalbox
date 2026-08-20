#!/usr/bin/env bash
# =============================================================================
# watch-localbox.sh — liveness-aware progress monitor for the in-VM automation.
#
# WHY THIS EXISTS
#   The DeploymentProgress resource-group tag is NOT a liveness signal. On
#   2026-08-20 it read "Configure Hyper-V host" for 80 minutes after the in-VM
#   script had already died. Trusting it cost more time than the actual bug.
#
#   This script cross-checks three independent signals:
#     1. the DeploymentProgress tag        (what it CLAIMS to be doing)
#     2. New-LocalBoxCluster.log mtime     (whether anything is ACTUALLY running)
#     3. the localcluster-validate ARM deployment (the gate that rejects a bad
#        OS image ~50 minutes in — the single most likely failure)
#
# USAGE
#   ./scripts/watch-localbox.sh              # poll every 5 minutes
#   ./scripts/watch-localbox.sh 60           # poll every 60 seconds
#   ./scripts/watch-localbox.sh 300 --once   # single check, for cron/CI
# =============================================================================
set -uo pipefail

INTERVAL="${1:-300}"
ONCE="${2:-}"
NODES_RG="${JS_NODES_RG:-rg-localbox-nodes-san-1}"
AZLOCAL_RG="${JS_AZURELOCAL_RG:-rg-localbox-azlocal-we-1}"
VM_NAME="${JS_VM_NAME:-LocalBox-Client}"
STALE_MINUTES="${STALE_MINUTES:-25}"

ts() { date '+%H:%M:%S'; }

probe_vm() {
  az vm run-command invoke -g "$NODES_RG" -n "$VM_NAME" \
    --command-id RunPowerShellScript --scripts '
$log = "C:\LocalBox\Logs\New-LocalBoxCluster.log"
if (Test-Path $log) {
  "LOGAGE=" + [math]::Round(((Get-Date) - (Get-Item $log).LastWriteTime).TotalMinutes,1)
} else { "LOGAGE=-1" }
$t = Get-ScheduledTask -TaskName LocalBoxLogonScript -ErrorAction SilentlyContinue
"TASK=" + $(if ($t) { $t.State } else { "absent" })
"VMS=" + ((Get-VM -ErrorAction SilentlyContinue | Where-Object State -eq "Running" | Measure-Object).Count)
' --query "value[0].message" -o tsv 2>/dev/null | grep -E '^(LOGAGE|TASK|VMS)='
}

check() {
  stage=$(az group show -n "$AZLOCAL_RG" --query tags.DeploymentProgress -o tsv 2>/dev/null || echo "?")

  probe=$(probe_vm)
  logage=$(printf '%s' "$probe" | sed -n 's/^LOGAGE=//p')
  task=$(printf '%s'   "$probe" | sed -n 's/^TASK=//p')
  vms=$(printf '%s'    "$probe" | sed -n 's/^VMS=//p')
  : "${logage:=?}" "${task:=?}" "${vms:=?}"

  validate=$(az deployment group show -g "$AZLOCAL_RG" --name localcluster-validate \
    --query "properties.provisioningState" -o tsv 2>/dev/null || echo "-")

  echo "[$(ts)] stage='${stage}' log_age=${logage}m task=${task} nested_vms=${vms} validate=${validate}"

  # --- terminal states -------------------------------------------------------
  if [ "$stage" = "Failed" ] || [ "$validate" = "Failed" ]; then
    echo "[$(ts)] FAILED. Pulling the specific error:"
    az deployment operation group list -g "$AZLOCAL_RG" --name localcluster-validate \
      --query "[?properties.provisioningState=='Failed'].{type:properties.targetResource.resourceType,code:properties.statusMessage.error.code,msg:properties.statusMessage.error.message}" \
      -o json 2>/dev/null | head -20
    echo "[$(ts)] In-VM log tail:"
    az vm run-command invoke -g "$NODES_RG" -n "$VM_NAME" --command-id RunPowerShellScript \
      --scripts 'Get-Content C:\LocalBox\Logs\New-LocalBoxCluster.log -Tail 25 | Out-String' \
      --query "value[0].message" -o tsv 2>/dev/null | tail -25
    return 2
  fi

  # --- liveness: the tag lies, the log does not ------------------------------
  if [ "$logage" != "?" ] && [ "$logage" != "-1" ]; then
    if awk -v a="$logage" -v s="$STALE_MINUTES" 'BEGIN{exit !(a>s)}'; then
      echo "[$(ts)] WARNING: log stale for ${logage}m (>${STALE_MINUTES}m) while tag says '${stage}'."
      echo "[$(ts)] This is the 'tag lies' failure mode. Log tail:"
      az vm run-command invoke -g "$NODES_RG" -n "$VM_NAME" --command-id RunPowerShellScript \
        --scripts 'Get-Content C:\LocalBox\Logs\New-LocalBoxCluster.log -Tail 25 | Out-String' \
        --query "value[0].message" -o tsv 2>/dev/null | tail -25
      return 2
    fi
  fi

  # --- success ---------------------------------------------------------------
  cluster=$(az resource list -g "$AZLOCAL_RG" --resource-type Microsoft.AzureStackHCI/clusters \
    --query "[0].name" -o tsv 2>/dev/null || echo "")
  if [ -n "$cluster" ] && [ "$validate" = "Succeeded" ]; then
    echo "[$(ts)] Cluster '$cluster' present and validation succeeded."
    az resource list -g "$AZLOCAL_RG" --query "[].{name:name,type:type}" -o table
    return 0
  fi
  return 1
}

echo "Monitoring LocalBox — nodes RG=$NODES_RG, Azure Local RG=$AZLOCAL_RG, interval=${INTERVAL}s"
echo "Liveness threshold: log must be written within ${STALE_MINUTES} minutes."
while true; do
  check; rc=$?
  [ "$rc" -eq 0 ] && echo "DONE: deployment complete." && exit 0
  [ "$rc" -eq 2 ] && echo "DONE: deployment failed — see above." && exit 1
  [ "$ONCE" = "--once" ] && exit 0
  sleep "$INTERVAL"
done
