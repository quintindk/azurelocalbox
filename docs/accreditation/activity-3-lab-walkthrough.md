# Activity 3 - Azure Local proof of concept, lab walkthrough

**Issue:** [#104](https://github.com/quintindk/TID/issues/104)
**Offering:** Workshop - Azure Local Foundations - 3 Day - Closed Workshop
**Activity:** 3 of 7
**Lab environment:** Azure Arc Jumpstart, **Jumpstart LocalBox** (the successor to
Jumpstart HCIBox), deployed via `azd` into a governed landing-zone spoke
**Prepared:** 19 August 2026
**Executed:** 21 August 2026

> **Evidence status: captured.**
> All thirteen `[capture]` items were produced from an actual run on
> 20-21 August 2026 and are indexed in the verification summary below. Nothing in
> this document is reconstructed from memory.
>
> **Corrections applied after execution.** Running this walkthrough verbatim
> failed five times, four of them in Step 4 alone. Every command below has been
> corrected against the CLI as it actually behaves (`stack-hci-vm` extension,
> August 2026). The original text is preserved in the "Corrections" appendix so
> the changes are auditable rather than silent.

---

## What this lab does and does not prove

Jumpstart HCIBox is a **nested virtualisation sandbox**. It runs an Azure Local instance inside an Azure VM, with virtual machines, a virtual switch fabric and a virtual storage layer. It is the right tool for demonstrating the **management plane**, which is what the accreditation scenario asks for, and it is the wrong tool for drawing any conclusion about performance.

**What it proves faithfully:**

- Arc registration and the resource model
- VM lifecycle through Azure Resource Manager
- Logical networking as ARM resources
- RBAC, monitoring and the update surface
- The operational workflow an engineer would actually use with a customer

**What it cannot prove, and must not be claimed to:**

- Storage performance, because the storage is virtual
- RDMA behaviour, since there is no real RoCE or iWARP fabric
- Hardware certification, firmware baselines or the real solution update path
- Genuine failure and rebuild timings

State this distinction in any customer conversation that references lab work. It is exactly the same caveat that applies to POC results generated on non-production hardware.

---

## Prerequisites

| Item | Requirement |
|---|---|
| Azure subscription | Owner, or Contributor plus User Access Administrator |
| Resource providers | `Microsoft.HybridCompute`, `Microsoft.GuestConfiguration`, `Microsoft.HybridConnectivity`, `Microsoft.AzureStackHCI`, `Microsoft.ResourceConnector`, `Microsoft.ExtendedLocation`, `Microsoft.KubernetesConfiguration`, **`Microsoft.EdgeMarketPlace`** |
| Region | One supported by LocalBox / Azure Local, for example `eastus` or `westeurope`. **South Africa North is not a supported Azure Local region** — register the instance elsewhere if the client VM lives there |
| Quota | The nested host is large. Confirm cores are available before deploying, this is the most common first failure |
| Local tooling | Azure CLI, Bicep, `azd`, and an SSH or Bastion path to the host VM |
| Service principal | **Not required.** The deployment runs as the signed-in user; role assignments target the client VM's managed identity |

> **`Microsoft.EdgeMarketPlace` is not optional and is easily missed.** Without
> it, everything deploys cleanly and then Step 4 fails when you request a
> Marketplace image, with
> `GenerateTokenFromEdgeMarketplaceServiceFailed / SubscriptionNotRegistered`.
> The failure surfaces hours after deployment and reads like a broken lab rather
> than a missing prerequisite. This was the single largest time loss in the run.

```bash
az login
az account set --subscription "<subscription-id>"

for rp in Microsoft.HybridCompute Microsoft.GuestConfiguration \
          Microsoft.HybridConnectivity Microsoft.AzureStackHCI \
          Microsoft.ResourceConnector Microsoft.ExtendedLocation \
          Microsoft.KubernetesConfiguration Microsoft.EdgeMarketPlace; do
  az provider register --namespace "$rp"
done

# Confirm every one reports Registered before continuing.
az provider list \
  --query "[?namespace=='Microsoft.AzureStackHCI'].{ns:namespace,state:registrationState}" \
  -o table
```

**[capture] Screenshot 1:** provider registration states, all `Registered`.

---

## Step 1 - Deploy or review an Azure Local instance

Deploy LocalBox. The deployment provisions the client VM, then a nested Azure
Local instance, and is largely unattended once it starts.

```bash
# azd project (the path used for this run)
azd env new localbox-san
azd env set JS_GITHUB_ACCOUNT <fork> && azd env set JS_GITHUB_BRANCH <branch>
azd provision
```

**Expect this to take several hours.** `azd provision` itself completed in ~12
minutes; the nested build took a further **2 h 45**. The portal reports the ARM
deployment as succeeded long before the instance is usable, so watch the client
VM's logs (`C:\LocalBox\Logs\New-LocalBoxCluster.log`) rather than ARM status.

> **The `DeploymentProgress` resource-group tag is not a liveness signal.** During
> this run it read `Configure Hyper-V host` for 80 minutes after the in-VM script
> had already died. Cross-check the log file's modification time and the
> `localcluster-validate` / `localcluster-deploy` ARM deployments.

**Verification:**

```bash
# The instance should appear as an Azure resource with a connected status.
az stack-hci cluster list -g <azure-local-rg> \
  --query "[].{Name:name,Status:status,Connectivity:connectivityStatus,\
Nodes:reportedProperties.nodes[].name,Version:reportedProperties.clusterVersion}" -o yaml

# The underlying machines should be present as Arc-enabled machines.
az connectedmachine list -g <azure-local-rg> \
  --query "[].{Name:name,Status:status,OS:osName,Agent:agentVersion}" -o table
```

**[capture] Screenshot 2:** the Azure Local resource in the portal, showing status Connected, the machine count and the current version. → `portal-02-instance-overview.png`, `cli-02-cluster-connected.png`
**[capture] Screenshot 3:** the Machines blade listing each node with its Arc agent connected. → `portal-03-machines-blade.png`, `cli-03-arc-machines.png`

**What to observe and note in the write-up:**

- The instance is a **resource in Azure**, with a resource ID, tags and RBAC, not merely a monitored device.
- Each machine appears as an **Arc-enabled machine in its own right**, which is what makes policy and extensions reach them.
- The **version and update status** are surfaced in the portal, which is the fleet compliance view a customer would use across many sites.

---

## Step 2 - Confirm the Azure Arc connection

Arc is not a separate step in a real deployment, since machines are Arc-enabled before the cluster is formed. The purpose here is to make the dependency visible and to inspect what it provides.

```bash
# On a node, inspect the Arc agent and its endpoint connectivity.
azcmagent show
azcmagent check
```

`azcmagent check` is the command worth demonstrating to a customer, because it enumerates the required endpoints and reports reachability for each. It converts an abstract firewall discussion into a concrete list.

> **Reaching a node.** In LocalBox the Azure Local nodes are nested VMs inside the
> client VM, so there is no direct path. Hop via PowerShell Direct from the client
> VM (the credential is read from the config file, so nothing sensitive appears
> on screen or in a screenshot):
>
> ```powershell
> $cfg  = Import-PowerShellDataFile C:\LocalBox\LocalBox-Config.psd1
> $cred = New-Object System.Management.Automation.PSCredential(
>           "jumpstart\Administrator",
>           (ConvertTo-SecureString $cfg.SDNAdminPassword -AsPlainText -Force))
> Invoke-Command -VMName AzLHOST1 -Credential $cred -ScriptBlock { azcmagent check }
> ```

**Then inspect the extensions and the Resource Bridge:**

```bash
az connectedmachine extension list \
  --machine-name <node-name> -g <azure-local-rg> -o table

# Note: 'az resource list' does not expand properties — status returns null.
# Use 'az resource show' to get the real state.
az resource show -g <azure-local-rg> -n <cluster>-arcbridge \
  --resource-type Microsoft.ResourceConnector/appliances \
  --query "{Name:name,Status:properties.status,Version:properties.version}" -o yaml
```

**[capture] Screenshot 4:** `azcmagent check` output showing endpoint reachability. → `cli-04-azcmagent-check.png`
**[capture] Screenshot 5:** the Arc Resource Bridge resource, showing a running state. → `portal-05-resource-bridge.png`, `cli-05-resource-bridge.png`

**Observed result (21 August 2026):** all seven core endpoints reachable, **TLS 1.3**,
`Proxy: not used`. This is the measured evidence that the secured-hub firewall
allowlist is correct **and** that no HTTPS break-and-inspect is occurring on the
Arc path (working specification, section 3.3).

**Talking points this step supports:**

- The **Resource Bridge** is what projects VM management into ARM, and its certificate is why an instance left un-updated beyond a year loses VM management functionality.
- The endpoint list is the substance behind the firewall conversation, including that **HTTPS break-and-inspect is unsupported**.
- Custom Location is the construct that lets an ARM deployment target this specific instance.

---

## Step 3 - Configure logical networking

Logical networks are created before VMs, because a VM needs one to attach to. Doing this step first also makes the point that networking is an ARM resource rather than a hypervisor setting.

Portal path: the Azure Local resource, then **Resources**, then **Logical networks**, then create.

```bash
az stack-hci-vm network lnet create \
  --resource-group <azure-local-rg> \
  --custom-location "$CL" \
  --name lnet-workload-static \
  --vm-switch-name "<switch-name>" \
  --ip-allocation-method "Static" \
  --address-prefixes "<prefix>" \
  --gateway "<gateway>" \
  --dns-servers "<dns>" \
  --ip-pool-start "<start>" --ip-pool-end "<end>"
```

> **Get the fabric values from the deployment, not from assumption.** In LocalBox
> the switch is `ConvergedSwitch(compute_management)`, the gateway is the router
> VM (`192.168.1.1`) and DNS is `192.168.1.254`; both are declared in
> `LocalBox-Config.psd1` as `SDNLABRoute` and `SDNLABDNS`. Also check the existing
> `<cluster>-InfraLNET` pool and pick a **non-overlapping** range — the infra pool
> is small and nearly exhausted.

**Verification:**

```bash
az stack-hci-vm network lnet list -g <azure-local-rg> \
  --query "[].{Name:name,Alloc:properties.subnets[0].properties.ipAllocationMethod,\
Prefix:properties.subnets[0].properties.addressPrefix,\
PoolStart:properties.subnets[0].properties.ipPools[0].start,\
PoolEnd:properties.subnets[0].properties.ipPools[0].end,\
State:properties.provisioningState}" -o table
```

**[capture] Screenshot 6:** the logical network resource with its address configuration and IP pool. → `portal-06-logical-network.png`, `cli-06-logical-networks.png`

**What to observe:**

- Both static pools and DHCP are supported, and the choice is per logical network.
- The network is an **ARM resource**, so it can be deployed as code, tagged and governed.
- Network security groups apply to Azure Local logical networks. This is worth stating explicitly because it is commonly assumed otherwise, and it was a correction raised on a live customer questionnaire.

---

## Step 4 - Create and manage a virtual machine

The core of the demonstration. Do it **through Azure**, not through Hyper-V Manager, because the entire point is that the control plane is Azure.

**First, make an image available:**

```bash
CL=$(az customlocation show -g <azure-local-rg> -n <cl-name> --query id -o tsv)

az stack-hci-vm image create \
  --resource-group <azure-local-rg> \
  --custom-location "$CL" \
  --name win2022-datacenter \
  --os-type Windows \
  --offer WindowsServer --publisher MicrosoftWindowsServer \
  --sku 2022-datacenter-azure-edition --version latest
```

> **This is the long pole and it has no `--no-wait`.** The download took
> **~75 minutes** over the nested fabric. Poll it in another shell rather than
> blocking:
> `az stack-hci-vm image show -g <rg> --name win2022-datacenter --query "{State:properties.provisioningState,Progress:properties.status.progressPercentage}" -o tsv`
> Detaching the CLI with Ctrl-C does not cancel the ARM operation.
>
> If this fails with `GenerateTokenFromEdgeMarketplaceServiceFailed`, the
> subscription is not registered to `Microsoft.EdgeMarketPlace`. Register it,
> delete the failed image resource, and retry.

**Then create a network interface.** The VM create takes a **NIC resource**, not
a logical network. This step is required and was missing from the original
walkthrough:

```bash
LNET=$(az stack-hci-vm network lnet show -g <azure-local-rg> \
         --name lnet-workload-static --query id -o tsv)

az stack-hci-vm network nic create \
  --resource-group <azure-local-rg> \
  --custom-location "$CL" \
  --name nic-accred-demo01 \
  --subnet-id "$LNET" \
  --location <region>
```

**Then create the VM:**

```bash
az stack-hci-vm create \
  --resource-group <azure-local-rg> \
  --custom-location "$CL" \
  --name vm-accred-demo01 \
  --location <region> \
  --image win2022-datacenter \
  --admin-username azureuser \
  --admin-password "<password>" \
  --computer-name vmaccreddemo01 \
  --size Standard_A2_v2 \
  --nics nic-accred-demo01 \
  --enable-agent true
```

> **Three things the original got wrong here.**
> 1. `--v-cpu-count` / `--memory-mb` no longer exist. Sizing is `--size` with a
>    named SKU; `Standard_A2_v2` is the 2 vCPU / 4 GB equivalent.
> 2. `--computer-name vm-accred-demo01` is **16 characters** and is rejected —
>    Windows caps computer names at 15. Keep the ARM resource name and shorten
>    only the guest name.
> 3. `--nics lnet-workload-static` fails with `... /networkInterfaces/lnet-workload-static does not exist`.
>    Pass the NIC created above.

`--enable-agent true` matters: it Arc-enables the guest, which brings Azure Policy, machine configuration, extensions and Defender for Servers to the workload rather than only to the platform.

**Then exercise the lifecycle:**

```bash
# Note: no --yes flag on stop in the current extension.
az stack-hci-vm stop  --name vm-accred-demo01 -g <azure-local-rg>
az stack-hci-vm start --name vm-accred-demo01 -g <azure-local-rg>

# Add a data disk and attach it, an everyday operational task.
az stack-hci-vm disk create \
  --resource-group <azure-local-rg> --custom-location "$CL" \
  --name disk-accred-data01 --size-gb 64 --dynamic true --location <region>

# --disks is plural, and the command prompts for confirmation.
az stack-hci-vm disk attach \
  --resource-group <azure-local-rg> \
  --vm-name vm-accred-demo01 --disks disk-accred-data01
```

**[capture] Screenshot 7:** the VM resource in the portal, showing it as an Azure resource with properties, tags and an Activity log. → `portal-07-vm-overview.png`, `cli-07-vm-created.png`
**[capture] Screenshot 8:** the VM running, with the attached data disk and the logical network connection visible. → covered by `portal-07-vm-overview.png` (the Overview blade shows both the 64 GB data disk and the NIC on `lnet-workload-static` at `192.168.1.150`)
**[capture] Screenshot 9:** the Activity log for the VM, showing the create, stop, start and update operations attributed to an Entra identity. → `portal-09-vm-activity-log.png`

> **Filtering Screenshot 9.** Lifecycle operations act on the
> `Microsoft.AzureStackHCI/virtualMachineInstances` child resource, not the
> `Microsoft.HybridCompute/machines` parent. Filtering the Activity log by
> `Resource: <vm-name>` hides them. Filter by **resource group**, and add
> **Event initiated by = <your account>** to strip Advisor, K8 Bridge and
> platform resource-provider noise.

Screenshot 9 is the most valuable single artefact from this lab. It shows infrastructure operations in a factory being audited through Azure, attributed to a named identity, in the same log stream as everything else. That is the operating-model argument made concrete.

---

## Step 5 - Demonstrate RBAC

Not listed separately in the task, but it is the strongest point the lab can make and it takes minutes.

```bash
# Grant a test principal VM-level rights only.
az role assignment create \
  --assignee "<test-user-object-id>" \
  --role "Azure Stack HCI VM Contributor" \
  --scope "/subscriptions/<sub>/resourceGroups/<azure-local-rg>"
```

> Capture the principal's assignments **before** the grant as well. A test user
> with zero existing assignments makes the scoping argument; a user who already
> had Reader proves nothing.

**[capture] Screenshot 10:** the role assignment, and the portal view as that user, able to manage the VM without any infrastructure rights. → `portal-10-rbac-assignment.png`, `cli-10-rbac-assignment.png`

**Note for the write-up:** the built-in roles are **still branded "Azure Stack HCI"**. There is no role named "Azure Local Administrator". Anyone searching for one concludes wrongly that the capability is missing, so it is worth flagging in a workshop before a delegate hits it.

**Second note:** the grant is scoped to the **resource group**, not to the Azure
Local instance resource. The VMs are ARM resources in the RG, and that is where
VM rights land. The natural assumption is the opposite.

---

## Step 6 - Monitoring and management through Azure

Enable Insights on the instance, which deploys the Azure Monitor Agent and wires it to a Log Analytics workspace.

Portal path: the Azure Local resource, then **Monitoring**, then **Insights**, then enable and select or create a workspace.

> **The workspace must be in the same region as the Azure Local instance.** If the
> only workspace is elsewhere, the picker appears empty with no explanation. In
> this run the deployment's own `LocalBox-Workspace` sat in South Africa North
> while the instance was registered in West Europe, so a West Europe workspace had
> to be created:
>
> ```bash
> az monitor log-analytics workspace create \
>   -g <azure-local-rg> -n law-localbox-we-1 --location <instance-region> \
>   --retention-time 30
> ```
>
> Put it in the same resource group as the instance so teardown removes it.

**Verification, once data has landed:**

```kusto
// Instance health and node reporting.
Event
| where TimeGenerated > ago(1h)
| summarize count() by Computer
```

```bash
# Confirm ingestion before screenshotting an empty dashboard.
WS=$(az monitor log-analytics workspace show -g <azure-local-rg> \
       -n law-localbox-we-1 --query customerId -o tsv)
az monitor log-analytics query -w "$WS" --analytics-query \
  "union * | where TimeGenerated > ago(1h) | summarize Rows=count() by Type" -o table
```

Data landed roughly 20 minutes after enablement.

**[capture] Screenshot 11:** the Insights dashboard, showing instance and node health, CPU, memory and storage utilisation. → `portal-11-insights.png`
**[capture] Screenshot 12:** an alert rule configured against the instance. → `portal-12-alert-rule.png`, `cli-12-alert-rule.png`

A log alert can be created without the portal wizard:

```bash
WSID=$(az monitor log-analytics workspace show -g <azure-local-rg> -n law-localbox-we-1 --query id -o tsv)
az monitor scheduled-query create -g <azure-local-rg> \
  -n "alert-azlocal-node-heartbeat" --scopes "$WSID" \
  --description "Azure Local node stopped reporting heartbeat for 10 minutes" \
  --condition "count 'heartbeat' < 1" \
  --condition-query heartbeat="Heartbeat | where Computer contains \"AzLHOST\" | summarize AggregatedValue=count() by bin(TimeGenerated,5m)" \
  --evaluation-frequency 5m --window-size 10m --severity 2
```

> The rule above has **no action group**, so it evaluates but notifies nobody.
> That is deliberate for a lab. Add an action group if the notification path
> itself needs to be demonstrated.

**What to observe:**

- The same monitoring surface as Azure resources, so no separate on-premises monitoring stack is required.
- Log ingestion is **billed as normal Azure Monitor consumption**, which belongs in the customer's cost model rather than being discovered later.
- Across many sites this is one dashboard, which is the fleet argument.
- The Insights **RDMA panel renders but is meaningless here** — the fabric is
  virtual. Do not present it as evidence of RDMA behaviour.

---

## Step 7 - Document operational tasks

### VM lifecycle

| Task | How | Notes |
|---|---|---|
| Create | Portal, CLI, ARM, Bicep or Terraform | Image and logical network must exist first |
| Start, stop, restart | Portal or `az stack-hci-vm` | Azure RBAC controlled, logged to the Activity log |
| Resize | `az stack-hci-vm update` | vCPU and memory |
| Add storage | `disk create` then `disk attach` | Dynamic or fixed |
| Delete | Portal or CLI | Disks are retained unless explicitly removed |
| Arc-enable the guest | `--enable-agent true` at create | Brings policy, extensions and Defender to the workload |

### Updates

Portal path: the Azure Local resource, then **Updates**.

```powershell
# On a node, inspect available solution updates.
Get-SolutionUpdate | Format-Table Version, State, InstalledDate

# Health check before applying.
Invoke-SolutionUpdate -ComputerName <node>
```

**[capture] Screenshot 13:** the Updates blade showing the current version, available updates and readiness checks.

**Points to make from this screen:**

- One package covering operating system, drivers, firmware and agents, validated together.
- Applied **cluster-aware**, one machine at a time, workloads staying online.
- A **rolling six month** support window from the latest release, so two to three updates a year.
- Health checks run before the update, and the results are visible in Azure.

> In HCIBox the firmware component of a solution update is not real, since the hardware is virtual. Say so rather than implying the lab validated a firmware path.

### Routine operational tasks worth listing in the deliverable

- Reviewing instance and node health in Insights
- Checking update compliance across the fleet
- Reviewing the Activity log for infrastructure changes
- Confirming the last Azure sync time, given the **30-day out-of-policy rule**
- Verifying backup jobs by restore, not by job success
- Reviewing Defender for Cloud recommendations, noting that Defender for Cloud on the Azure Local instance is **preview**
- Confirming the security baseline has not drifted
- Capacity headroom review against the rebuild reserve

---

## Verification summary

Completed during the run of 20-21 August 2026. Evidence screenshots are held
locally in `evidence/` alongside this document and are deliberately not
committed — they carry tenant, subscription and workstation detail. Request
them directly for accreditation submission.

| # | Step | Verification | Evidence | Result |
|---|---|---|---|---|
| 0 | Prerequisites | All required providers `Registered` | `cli-01-provider-registration.png`, `portal-01-resource-providers.png` | Pass |
| 1 | Instance deployed | Resource present, status Connected | `cli-02-cluster-connected.png`, `portal-02-instance-overview.png`, `cli-03-arc-machines.png`, `portal-03-machines-blade.png` | Pass — `localboxcluster`, Connected, 2 nodes, build 26100.32690 |
| 2 | Arc connected | `azcmagent check` passes, bridge running | `cli-04-azcmagent-check.png`, `cli-05-resource-bridge.png`, `portal-05-resource-bridge.png` | Pass — 7/7 endpoints reachable, TLS 1.3, no proxy; bridge Running 1.7.0 |
| 3 | Logical network | Network resource with IP pool | `cli-06-logical-networks.png`, `portal-06-logical-network.png` | Pass — `lnet-workload-static`, static pool .150-.170 |
| 4 | VM created and managed | VM running, disk attached, lifecycle in Activity log | `cli-07-vm-created.png`, `portal-07-vm-overview.png`, `portal-09-vm-activity-log.png` | Pass — VM Arc-enabled (agent 1.67), 64 GB data disk, IP .150 from pool |
| 5 | RBAC | VM managed without infrastructure rights | `cli-10-rbac-assignment.png`, `portal-10-rbac-assignment.png` | Partial — assignment captured and scoped correctly; **the "view as that user" half was not captured** |
| 6 | Monitoring | Insights reporting, alert rule configured | `portal-11-insights.png`, `cli-12-alert-rule.png`, `portal-12-alert-rule.png` | Pass — both nodes Healthy, Perf/Heartbeat/Event ingesting; heartbeat alert enabled |
| 7 | Updates | Update surface and readiness checks visible | `cli-13-solution-update.png`, `portal-13-updates-blade.png` | Pass — readiness Healthy, 2026.08 Cumulative Update 12.2608.1003.8 available |

### Known gaps and blemishes in the evidence

Recorded deliberately rather than omitted:

- **Item 5 is incomplete.** The role assignment is proven; the second half — that
  principal signing in and managing the VM with no infrastructure visibility —
  was not captured. Claim only what the evidence shows.
- **Screenshot 8 has no dedicated file.** The VM Overview blade shows the data
  disk and the NIC together, so it serves both 7 and 8.
- **Two failed operations appear in Screenshot 9**: an `auditIfNotExists` policy
  action and a `Create or Update Virtual Machine Extension` (the Defender/MDE
  extension on the guest). Neither affects the platform result, but both are
  visible and should be explained rather than left for an assessor to find.
- **Screenshot 12 shows an unrelated alert rule** from another subscription
  (`fabshield-scan-failure-alert`) because the blade's subscription filter was
  set to three subscriptions.
- **The post-deployment test suite reported 11 passed, 1 failed.** The failure is
  `should have 25 resources or more`: this deployment splits resources across two
  resource groups, so the Azure Local RG holds 24. Cosmetic, caused by the
  two-RG governed topology, not a defect.

---

## Corrections appendix

Applied 21 August 2026 after executing the walkthrough. The original text failed
in the following places.

| # | Original | Problem | Correction |
|---|---|---|---|
| 1 | Provider list omits `Microsoft.EdgeMarketPlace` | Step 4 image creation fails with `GenerateTokenFromEdgeMarketplaceServiceFailed` / `SubscriptionNotRegistered`, hours after deployment | Added to prerequisites |
| 2 | `--v-cpu-count 2 --memory-mb 4096` | Arguments do not exist in the current `stack-hci-vm` extension | `--size Standard_A2_v2` |
| 3 | `--computer-name vm-accred-demo01` | 16 characters; Windows limit is 15 | `--computer-name vmaccreddemo01` |
| 4 | `--nics lnet-workload-static` | `--nics` takes a NIC resource, not a logical network | Added the missing `network nic create` step |
| 5 | `az stack-hci-vm stop ... --yes` | No `--yes` flag on this command | Removed |
| 6 | `disk attach --disk-name` | Argument is `--disks` (plural) and prompts for confirmation | Corrected |
| 7 | `az stack-hci-vm update --memory-mb 8192` | No such resize path in the current extension | Removed from the lifecycle sequence |
| 8 | `az resource list` for the Resource Bridge | Does not expand properties; status returns `null` | `az resource show` |
| 9 | Environment described as "Jumpstart HCIBox", RG `rg-hcibox-accred`, region `eastus` | Run used Jumpstart LocalBox, a governed spoke, and West Europe registration | Placeholders and environment line corrected |

Items 1 and 4 are the material ones: both produce failures that read as broken
infrastructure rather than as documentation defects.

---

## Execution notes

**Time.** Budget roughly half a day. Actual for this run: `azd provision` 12
minutes, nested build 2 h 45, Marketplace image download ~75 minutes, evidence
capture ~2 hours. The image download is the hidden cost — it is not mentioned in
the original walkthrough and it blocks Step 4 entirely, so **start it as soon as
the instance is up** and work Steps 5 to 7 while it runs.

**Cost.** The nested host is a large VM (`Standard_E32s_v6` for this run).
**Deallocate it as soon as the evidence is captured** and delete the resource
group afterwards. Leaving it running over a weekend is an expensive way to learn
this.

**The most likely failure is quota**, not configuration. Confirm the core quota in the target region before deploying, because the failure appears late and wastes the whole cycle.

**Second most likely: silent failures in the nested build.** Two cost ~5 hours on
the first attempt of this run, both in the Jumpstart automation rather than in
Azure:

- The Azure Local VHDX was fetched from a storage account returning
  `403 AccountIsDisabled`, and `azcopy`'s exit code was never checked.
- The checksum gate compared `$null` to `$null` and passed, so an absent 30 GB
  image reported "valid checksum" and failed 40 minutes later with a misleading
  "source VHDX not found".

Validate image URLs before deploying; a two-second `curl` beats a ninety-minute
diagnosis.

**Sequencing against the accreditation deadline.** This is the only one of the seven activities that cannot be completed from the desk, so it is the constraint on the end-of-August commitment. Activities 1, 2, 4, 5, 6 and 7 are complete. Book the lab window first and let the rest of the pack wait on nothing.

**Deployment path used (20 August 2026).** HCIBox deployed via the Jumpstart jumpbox pattern into an enterprise landing zone behind a secured virtual WAN, rather than a standalone subscription. This is the pattern Jumpstart recommends for landing-zone-aligned deployments and it is a supported route. Two consequences worth recording as they are captured:

- Outbound egress traverses the secured hub, so the firewall policy has to permit the Azure Local and Arc endpoint set, and must not perform HTTPS break and inspect on the Arc path (see the working specification, section 3.3). Any evidence screenshot showing a failed Arc registration should be checked against firewall policy before configuration.
- The jumpbox is the management surface for the lab, so portal screenshots are taken from inside the landing zone rather than from a workstation. Note this against the evidence items so the assessor understands the network context.

## References

| Topic | Link |
|---|---|
| Azure Arc Jumpstart, HCIBox | https://jumpstart.azure.com/azure_jumpstart_hcibox |
| Create Azure Local VMs | https://learn.microsoft.com/en-us/azure/azure-local/manage/create-arc-virtual-machines |
| Logical networks | https://learn.microsoft.com/en-us/azure/azure-local/manage/create-virtual-networks |
| VM image management | https://learn.microsoft.com/en-us/azure/azure-local/manage/virtual-machine-image-azure-marketplace |
| Built-in RBAC roles for VM management | https://learn.microsoft.com/en-us/azure/azure-local/manage/assign-vm-rbac-roles |
| Monitoring with Insights | https://learn.microsoft.com/en-us/azure/azure-local/manage/monitor-single-23h2 |
| Solution updates | https://learn.microsoft.com/en-us/azure/azure-local/update/about-updates-23h2 |
| Arc agent and connectivity checks | https://learn.microsoft.com/en-us/azure/azure-arc/servers/azcmagent |
| Environment / readiness checker | https://learn.microsoft.com/en-us/azure/azure-local/manage/use-environment-checker |
| Azure Local Supportability TSGs | https://github.com/Azure/AzureLocal-Supportability/tree/main/TSG |
| LENS workbook | https://github.com/Azure/AzureLocal-LENS-Workbook |

### Internal guidance

This walkthrough was written independently of the SSG IPKIT workshop material and
reconciled against it afterwards. Read the gap analysis before the next run.

| Item | Location |
|---|---|
| IPKIT Lab Manual (L400, 12 optional M09 labs) | `SSG IP Development - IPKIT/Lab instructions - Optional module/Lab Manual.html` |
| IPKIT instructor guidance | `SSG IP Development - IPKIT/Lab instructions - Optional module/Instructor-guidance.md` |
| Reconciliation of the two | [`ipkit-gap-analysis.md`](ipkit-gap-analysis.md) |
