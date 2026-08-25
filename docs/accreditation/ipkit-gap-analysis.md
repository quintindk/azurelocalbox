# Gap analysis — IPKIT Lab Manual vs. this repo's Activity 3 run

**Guidance assessed:** `SSG IP Development - IPKIT / Lab instructions - Optional module`
— `Lab Manual.html` (Azure Local L400, 12 labs, ~6.5 h), `Instructor-guidance.md`,
`readme.md`, `Lab Manual.md`.
**Work assessed:** `activity-3-lab-walkthrough.md`, executed 20–21 August 2026 on
Jumpstart LocalBox in a governed spoke.
**Prepared:** 25 August 2026.

---

## 0. Was the guidance consulted?

No. The walkthrough was written from the accreditation activity brief and the
Jumpstart documentation. There are zero references to the IPKIT manual anywhere
in this repository, and the run predates this analysis. This document is a
retrospective reconciliation, not a record of intent.

That matters more than the coverage table below, because three specific pieces of
the guidance would have prevented failures we actually hit. See section 4.

---

## 1. The two documents are not the same artefact

Reconciling them line by line would be wrong. They have different jobs:

| | IPKIT Lab Manual | This repo's walkthrough |
|---|---|---|
| Purpose | Optional module M09, attendee-facing hands-on | Accreditation Activity 3, assessor-facing evidence |
| Structure | 12 independent labs, 3-checkbox contract each | 7 sequential steps, evidence table |
| Environment | Pre-staged jumpbox **or** customer 2-node cluster | Self-deployed LocalBox in a governed spoke |
| Status | "Best effort", explicitly skippable | Deliverable with a deadline |
| Fidelity assumption | Cluster already exists and is healthy | Deployment itself is part of the exercise |

So the correct question is not "did we do all 12 labs" — it's "does our run
leave us able to deliver M09". Mostly no.

---

## 2. Coverage map

| IPKIT lab | Scope | Our coverage | Detail |
|---|---|---|---|
| 01 Portal cluster deployment walk-through | ALCO | **Partial** | We deployed for real via `azd`, which is more than the lab asks. But we never walked the seven portal wizard tabs and never ran pre-flight validation. Lab 01's verification item "name each of the seven wizard tabs" is unmet |
| 02 Network ATC intents and verification | Both | **Absent** | Our Step 3 covers *logical networks* — an ARM resource. ATC is host networking: SET teaming, SMB-MC pairing, DCB/QoS. Different layer entirely. Not touched |
| 03 Arc-enabled VM via portal | ALCO | **Full** | Our Step 4. We used CLI rather than portal, which is a fair substitution — both hit the same RP |
| 04 Same VM via Bicep + Az CLI | ALCO | **Partial** | We used Bicep for the *landing-zone infrastructure*, not for the Arc VM. No `what-if` idempotency proof, which is the whole point of the lab |
| 05 Storage resiliency — retire a drive, watch rebuild | Both | **Absent** | See section 3 — we ruled this out on a flawed premise |
| 06 Security drift check + remediation report | Both | **Absent** | `Get-SecurityBaseline`, `Sync-AzsSecurity`, `Get-DriftRemediationReport`. Untouched, despite the Contoso spec asserting ~99 % baseline compliance |
| 07 AKS Arc + sample workload | ALCO | **Absent** | LocalBox supports it. Not attempted |
| 08 Azure Backup for an Arc VM | ALCO | **Absent** | Not attempted |
| 09 LENS workbook, eight tabs | ALCO | **Partial** | Our Step 6 proved Insights is ingesting and built an alert rule. We never imported LENS, which the instructor guidance links explicitly |
| 10 AUM update cycle | ALCO | **Partial** | Our Step 7 showed the update *surface* and an available 2026.08 CU. Lab 10 requires `State = Installed` and a no-outage rolling run. We proved availability, not the cycle |
| 11 Drain + swap + resume node | Both | **Absent** | `Suspend-ClusterNode -Drain` / `Resume-ClusterNode -Failback`. Pure Failover Clustering, works fine nested, 30 minutes |
| 12 End-to-end Bicep — logical network + VM | ALCO | **Absent** | Depends on a lab repo that does not exist (section 5) |

**Tally: 1 full, 4 partial, 7 absent.**

Two things we did that the manual does not ask for at all:

- **Step 5, RBAC.** No IPKIT lab covers role scoping. The accreditation brief
  required it. Keep it.
- **The governed-spoke `azd` deployment.** Entirely outside M09's scope and the
  more transferable asset of the two.

---

## 3. The storage-resiliency call was wrong

Our walkthrough states, correctly, that nested LocalBox cannot prove storage
*performance*, RDMA, or hardware certification. It then declines Lab 05 on that
basis. That conflates two different claims.

Lab 05 tests **resiliency behaviour**, not throughput: `Set-PhysicalDisk -Usage
Retired`, watch `Get-StorageJob`, confirm `Get-VirtualDisk` returns to `Healthy`,
confirm no VM downtime. Every one of those operates on the virtual storage stack
and returns truthful results nested. IPKIT scopes it **Both** — meaning it is
valid on simulated environments — and we scoped it out anyway.

Same reasoning error applies to Lab 11 (drain/resume) and Lab 02 (ATC status),
both also scoped **Both**.

**Net: all three labs IPKIT considers simulation-safe were skipped, and the two
we did most thoroughly are ALCO-only.** That is the inverse of the right priority
for a nested lab.

---

## 4. Guidance that would have saved us time

This is the part that costs money.

| Guidance we ignored | What it would have prevented |
|---|---|
| **"Deploy the jumpbox at least 1 week before the workshop (2–4 h provisioning plus smoke-test)."** We prepared on 19 August and executed on 21 August, against a deployment that failed five times | The entire schedule risk. Our own execution notes concede this activity is the constraint on the end-of-August commitment. The guidance said so up front |
| **Readiness checker / Environment Checker**, linked in `Instructor-guidance.md` and used as Lab 01 step 8 | Quota and endpoint problems surface before an hours-long deploy, not after. Our notes name quota as "the most likely failure" — the checker exists precisely for that |
| **`Azure/AzureLocal-Supportability` TSGs and the Azure Local Wiki**, both linked in the guidance | We debugged five failures blind, including `GenerateTokenFromEdgeMarketplaceServiceFailed`. The TSG repo is the first place that class of error is documented |
| **Troubleshooting cheat sheet** in the Lab Manual | Directly covers `CustomLocation not found`, stalled `aksarc create`, stuck S2D rebuilds, empty LENS tabs, and Backup region mismatch. We rediscovered a subset of this the expensive way |

Also worth registering: the guidance says M09 is **optional and best-effort**,
with an explicit instruction that a red check means "move on without blocking".
We treated the lab as blocking and burned five deploy cycles on it. The
accreditation brief may well justify that. The guidance did not.

---

## 5. Defects in the IPKIT manual, found by actually running it

Our run is the field test this manual has not had. These should go back to the
IP owner.

1. **The lab repo does not exist.** Labs 04 and 12 both `git clone
   https://github.com/<lab-org>/azure-local-l400-labs.git`. The placeholder was
   never filled. Lab 12 is unrunnable as written, and Lab 04 is unrunnable
   without it.
2. **Lab 04 step 7 uses `az vm show --ids <Arc VM resource id>`.** Wrong command
   family for Arc VMs on Azure Local — it is `az stack-hci-vm show`. `az vm show`
   will not resolve the resource.
3. **Lab 12 step 8 specifies `vmSize: Standard_K8s_v1`.** Not a valid size. Our
   run established the working value is a standard SKU string such as
   `Standard_A2_v2`.
4. **`Microsoft.EdgeMarketPlace` is absent from every prerequisite list.** Lab 03
   assumes a "pre-uploaded Windows Server 2022 Datacenter Gen2" image. If the
   environment instead pulls from Marketplace — which any self-deployed lab env
   will — image creation fails hours in with
   `GenerateTokenFromEdgeMarketplaceServiceFailed`. This is documented in our
   corrections appendix, item 1.
5. **Marketplace image download time is unbudgeted.** ~75 minutes in our run, and
   it hard-blocks Lab 03. A 45-minute lab slot cannot absorb it.
6. **Lab 03 hands attendees a self-chosen 16-character password with no recovery
   path,** flagged only in a ⚠ box. For a cohort, that will generate support load.
7. **Naming conventions diverge from any real deployment.** The manual mandates
   `lab03-<initials>-vm`, `lab04-<initials>-rg`, and says "don't customise
   resource names". Our governed spoke uses `rg-localbox-azlocal-we-1`,
   `localboxcluster`, `lnet-workload-static`. Attendees on a landing-zone-aligned
   environment cannot follow the manual literally.

---

## 6. What to do

**To become deliverable on M09, in cost order:**

| Priority | Action | Cost |
|---|---|---|
| 1 | Run Labs 11, 06 and 05 on the existing LocalBox build. All scoped **Both**, all valid nested, all cheap | ~1.5 h |
| 2 | Complete Lab 10 properly — apply the staged 2026.08 CU and capture `State = Installed` with no workload outage | ~1 h, mostly waiting |
| 3 | Import the LENS workbook to close Lab 09 | 30 min |
| 4 | Read-only Lab 02 — capture `Get-NetIntentStatus` and `Get-VMSwitch` from the pre-configured LocalBox intents | 15 min |
| 5 | Write the missing `azure-local-l400-labs` Bicep content to close Labs 04 and 12. This repo already has the Bicep skeleton to adapt | Half a day |
| 6 | Labs 07 and 08 — AKS Arc and Azure Backup. Resource-heavy, lowest ratio | ~2 h |

**Regardless of the above:**

- Run the Environment Checker before any future deploy. Non-negotiable.
- Add the IPKIT manual and instructor guidance to the walkthrough's References
  section, so the next run starts from the guidance rather than beside it.
- Send section 5 to the IP owner. Seven concrete defects from a real run is the
  most useful thing this exercise produced.
