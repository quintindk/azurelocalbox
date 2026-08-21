# Contoso Manufacturing - working specification

**Issue:** [#104](https://github.com/quintindk/TID/issues/104)
**Scenario:** [`accreditation-scenario-contoso.md`](./accreditation-scenario-contoso.md)
**Status:** WORKING DOCUMENT. Internal. Not a deliverable.
**Last updated:** 19 August 2026

---

## What this document is

The master specification for the Contoso Manufacturing accreditation scenario. It carries the full design position, the constraints behind it, and the sourced facts each decision rests on.

The accreditation deliverables are generated **from** this document, not instead of it. Nothing here is length constrained, so positions can be worked out in full and cut down per deliverable.

| Deliverable | Length | Source sections |
|---|---|---|
| 1. Customer assessment | 1-2 pages | 1, 4, 5, 9 |
| 2. Architecture design and rationale | 5-10 slides | 2, 3, 6, 12, 13, 14, 15, 16 |
| 4. Migration strategy | Document | 7, 8 |
| 5. Executive presentation | 10-15 slides | 1, 6, 8, 11, 16 |
| 6. Customer meeting talking points | Document | 1, 6, 8, 11, 14, 16, 17 |
| 7. Knowledge validation | Written answers | 2, 3, 6, 12, 13, 16, 17 |

Sections 1 to 11 carry the assessment and migration position. Sections 12 to 17 carry the design domains required by activity 2: identity, Azure Arc integration, security, governance, business continuity and disaster recovery, and operational lifecycle management. Section 18 carries the sources.

Prose is written customer-ready so that deliverables extract without rewriting.

---

## Purpose of the engagement

This specification sets out the proposed platform topology for Contoso Manufacturing's VMware exit, the constraints that shape it, the assumptions and risks carried before discovery, and the information required from Contoso to complete the design.

Where a decision depends on information not held, the decision, the options and the closing question are stated together.

---

## 1. Drivers

The VMware licensing renewal sets the timeline. Contoso have committed to an 18-month exit, which places the platform decision early enough for 300 virtual machines to migrate at a pace the manufacturing business can absorb.

| Driver | How Azure Local addresses it |
|---|---|
| Reduce virtualisation licensing cost | Per physical core subscription billed through Azure, with Azure Hybrid Benefit available to existing Windows Server Datacenter customers (section 6) |
| Retain on-premises control and data residency | Workloads remain in Contoso's datacentres. Only management plane traffic reaches Azure |
| Hybrid cloud operating model | Azure Arc makes Azure the control plane for on-premises infrastructure |
| Reduce operational complexity | A single update mechanism and management surface across all locations |
| Integrate with Azure services | Native integration with Azure Arc, Azure Monitor, Update Manager, Microsoft Defender for Cloud and Azure Policy |
| Support future AI and edge initiatives | AKS enabled by Azure Arc, and GPU support within the Azure Local supported hardware list |

Contoso operate centralised operations and security teams across 25 sites, so the cost of retraining those teams is material to any platform change. Azure Local retains Hyper-V, Failover Clustering, Windows Admin Center and PowerShell, which shortens that path compared with alternatives.

---

## 2. Proposed topology

The architecture is drawn in [`azure-local-architecture.drawio`](./azure-local-architecture.drawio), which is the deliverable for activity 2. It presents four levels of increasing detail: the Azure control plane and services, the Azure Local instance workloads and platform, the physical topology and wide area connectivity with the switched datacentre and the storage switchless manufacturing site side by side, and the Storage Spaces Direct storage architecture.

![Contoso Manufacturing Azure Local target architecture](azure-local-architecture.drawio.svg)

Contoso are not deploying one platform. The datacentre estate and the manufacturing sites carry different workloads, different availability requirements and different operational realities. We propose two designs under one operating model.

### 2.1 Datacentre design

**Multiple clusters of up to 16 nodes per datacentre.**

The node ceiling depends on the deployment model, and the figures are frequently quoted without that qualification:

| Deployment model | Maximum machines per system |
|---|---|
| Hyperconverged, using Storage Spaces Direct | 16 |
| Rack aware | 8 |
| Disaggregated, using external SAN storage | 64 |
| Multi-rack, integrated racks | Hundreds. **Preview**, minimum four racks, and a narrower control plane region list |

We propose the **hyperconverged** model for Contoso, so **16 is the applicable ceiling**. We propose multiple systems per datacentre rather than one large system, separating workloads by lifecycle, blast radius and licensing boundary. SQL Server in particular should sit on a dedicated system, for the reasons set out in section 6.4.

**External SAN storage may be an option, depending on what underpins the VMware estate today.** The brief does not say (assumption 9). Azure Local supports Fibre Channel and iSCSI SAN arrays, presented as Cluster Shared Volumes, operating side by side with Storage Spaces Direct, and the disaggregated model raises the ceiling to 64 machines while allowing compute and storage to scale independently.

We raise it because the answer changes the hardware position rather than because we know it applies. If Contoso's datacentre storage is vSAN, it retires with VMware and the hyperconverged design above stands unchanged. If it is a Fibre Channel or iSCSI array with support life remaining, the disaggregated model is worth evaluating against assumption 6, since reusing it would reduce the procurement on the critical path described in section 8.1.

Two constraints apply either way: Storage Spaces Direct is still required at a minimum for the infrastructure volume and cluster performance history, which means at least two physical disks per node; and rack aware clusters are not supported with external SAN storage in hyperconverged deployments. Section 9 asks what the storage platform is.

| Attribute | Position |
|---|---|
| Nodes per system | Up to 16, sized to workload rather than to the ceiling |
| Systems per datacentre | Multiple, split by workload lifecycle, maintenance window and licensing boundary |
| SQL Server | Dedicated system, node count constrained by licensing (section 6.4) |
| Storage resiliency | Three-way mirror at four nodes and above |
| Storage network | Fully switched. Storage switchless is not available above four nodes |
| Witness | Cloud witness in Azure, or file share witness where connectivity requires it |
| Connectivity | Existing ExpressRoute |

### 2.2 Manufacturing site design

**One three-node storage switchless system per site, at twelve sites.**

Three nodes gives node-level fault tolerance with three-way mirror resiliency, and storage switchless removes the dedicated storage switches from twelve remote sites where there is no local IT presence to maintain them.

| Attribute | Position |
|---|---|
| Nodes per site | 3 |
| Storage network | Switchless, full mesh, direct connect between nodes |
| Management and compute network | Two ToR switches in MLAG. See 2.3 |
| Storage resiliency | Three-way mirror |
| Witness | Cloud witness, subject to WAN resilience at each site |
| Operations | Remote, through Azure Arc |

### 2.3 Storage switchless does not mean switchless

This distinction materially affects the bill of materials for the twelve manufacturing sites.

The Azure Local three-node storage switchless reference patterns still require **two ToR switches in a multi-chassis link aggregation group** for northbound and southbound traffic. Direct connect eliminates the dedicated **storage** switches, not the site's switching.

Each manufacturing site therefore requires:

- Two ToR switches in MLAG, carrying management and compute traffic through a SET virtual switch, with each network card connected to a different ToR
- Two or four RDMA network cards per node in full mesh for east-west storage traffic, depending on whether single link or dual link is selected
- No dedicated storage switches

Twelve sites at two switches per site requires twenty-four switches to procure, configure and maintain. This is a smaller switching estate than a fully switched design, but it is not eliminated.

### 2.4 Constraints on the switchless design

Three published constraints affect this topology and should be confirmed during design rather than encountered during deployment.

| Constraint | Consequence for Contoso |
|---|---|
| Storage switchless supports 1, 2, 3 or 4 nodes only | A site cannot exceed four nodes without redesigning to a switched storage fabric |
| Scale-out operations from the Azure portal or ARM are not supported on storage switchless deployments | A three-node site cannot be grown through the normal management path. Site growth means a rebuild or a redesign |
| Network ATC does not support storage network autoIP on three-node switchless deployments | IP and subnet addressing must be planned manually for each of the twelve sites |

We recommend Contoso accept these constraints for the manufacturing sites on the basis that those sites are unlikely to grow beyond three nodes, and confirm that assumption during discovery. If any site is expected to scale, it should be designed switched from the outset.

A further consideration: as node count grows beyond two, the cost of RDMA network cards can exceed the cost of switches. At three nodes with dual link, each node carries four RDMA cards. Contoso should compare that cost against a switched design before committing.

### 2.5 What manual storage addressing actually means

The autoIP constraint above is the single most repeated task in this programme, so it is worth stating concretely rather than as a caveat.

On the three-node dual link pattern, storage traffic runs over **six individual subnets**, one per node interconnect, isolated with no connectivity to other resources. Because Network ATC cannot assign these automatically at three nodes switchless, deployment sets `StorageAutoIP` to false and `Switchless` to true, and the addresses are specified explicitly in the ARM template used to deploy the instance.

Across twelve sites that is seventy-two storage subnets to plan, allocate and record without a single transposed digit. We recommend a single addressing standard, generated rather than hand-typed, and applied identically at every site.

---

## 3. Network requirements

Network readiness is a frequent source of delay in Azure Local deployments. The following should be established before any location commits to a migration date.

### 3.1 Datacentre network questions

1. What is the current datacentre network architecture: leaf and spine, or a traditional three-tier core, aggregation and access design?
2. Which switch make, model and firmware are deployed at top of rack?
3. Do the ToR switches support the required data centre bridging capabilities: priority flow control, enhanced transmission selection, and the DCBX protocol?
4. Which RDMA protocol will be used, RoCE or iWARP? The network cards installed determine which options are available, since RDMA adapters interoperate only with adapters implementing the same protocol. NVIDIA and Mellanox ConnectX is RoCE. Chelsio is iWARP. Marvell and QLogic support both.
5. If RoCE is selected, is the switching fabric capable of lossless transport with PFC configured end to end on the storage path?
6. What port capacity and speed is available at top of rack, and is 25 GbE or higher available for storage?
7. Are the ToR switches capable of MLAG or an equivalent, and are they already paired?
8. What VLAN ranges are available, and who administers them?
9. Where are the layer 3 boundaries, and are the storage VLANs terminated at the ToR without a switched virtual interface on the aggregation layer?
10. What is the current oversubscription ratio between access and aggregation?

### 3.2 Manufacturing site network questions

11. What switching exists at each manufacturing site today, and what is its age and support status?
12. Is there capacity for two ToR switches per site, and can they be configured in MLAG?
13. What is the WAN connectivity at each site: bandwidth, latency, provider and resilience?
14. Is outbound internet access available directly, or does all traffic backhaul to a datacentre?
15. Are the sites on a common network standard, or does each site differ?

### 3.3 Constraints to design against

The following apply to every Azure Local deployment and should be reflected in Contoso's network design and firewall change requests.

- **Outbound access requires ports 80 and 443.** Port 443 alone is not sufficient.
- **Storage traffic is SMB, layer 2, and not routable.** Storage adapters are single-purpose interfaces. Management, compute and any traffic requiring north-south communication cannot use the storage network adapters.
- **HTTPS break and inspect is not supported** anywhere on the Azure Arc path. This also precludes Microsoft Entra ID tenant restrictions version 1.
- **The proxy bypass list must be planned before Azure Arc registration.** Correcting it afterwards is disruptive. Azure Arc endpoints must resolve to public addresses from three places: the nodes, the Azure Arc Resource Bridge virtual machine, and the proxy server itself.
- **The Azure Arc gateway**, available from Azure Local 2506 for new deployments, substantially reduces the endpoint allowlist and therefore the size of the firewall change request. It is generally available for infrastructure and Azure Local virtual machines, and in preview for AKS. It does not carry HTTP, so HTTP endpoints still require separate allowance.
- **A minimum of two network adapter ports must be dedicated to storage traffic** on every multi-node system.
- **Azure Local has no stretched cluster equivalent** to VMware metropolitan patterns that rely on synchronous array replication. Microsoft state the position directly: stretched clusters are not supported in Azure Local. Site-level disaster recovery must be designed through replication and Azure services. See section 16.
- **A connected instance must sync with Azure at least once every 30 consecutive days.** This is the constraint most often discovered late, and it bears directly on twelve remote manufacturing sites whose Azure path runs over the corporate wide area network. On exceeding it the instance shows as *Out of policy* and enters a reduced functionality mode: the host infrastructure stays up and running virtual machines are unaffected, but **new virtual machines cannot be created** until the instance syncs again. A site that loses its WAN for a month therefore keeps producing, but cannot be changed. Section 16 treats this as a business continuity input, not merely a connectivity one.

We recommend Contoso run the Azure Local Environment Checker connectivity validator at a representative site early, and share the resulting endpoint data file with the firewall team as a single change request rather than iterating.

---

## 4. Assumptions

We have made the following assumptions to progress the assessment. Each changes the design if it proves wrong, and we ask Contoso to confirm or correct them.

1. The 300 virtual machines are distributed across all 15 locations rather than concentrated in the three datacentres.
2. Manufacturing site workloads affect production, so a site outage interrupts operations rather than office productivity.
3. Manufacturing sites will not exceed three nodes within the life of the platform.
4. ExpressRoute terminates at the datacentres. The manufacturing sites connect over the corporate wide area network.
5. SQL Server workloads do not depend on VMware-specific features. We make **no** assumption about SQL Server licensing, which is addressed in section 6.4 and requires confirmation from Contoso.
6. Hardware will be procured new from the Azure Local catalogue rather than repurposed from the existing VMware estate. The one case that would reopen this is an existing Fibre Channel or iSCSI array with support life remaining, which the disaggregated deployment model could reuse (section 2.1). See assumption 9.
7. The 18-month exit period runs from the licensing renewal date.
8. The brief refers to 25 sites across North America and Europe, while the infrastructure detail identifies 3 datacentres and 12 remote manufacturing sites. We have scoped this specification to those 15 locations and assume the remaining 10 sites carry no virtualisation infrastructure in scope. This requires confirmation, as it materially affects the deployment count.
9. **The brief does not describe the storage platform underpinning the VMware estate.** It states neither vSAN, nor an external array, nor local disk. We have assumed nothing, and have designed on Storage Spaces Direct with new hardware per assumption 6. This is a material unknown rather than a detail: it determines whether any existing storage investment survives the VMware exit, it changes the hardware volume on the critical path, and it affects the disposition exercise in section 8.2. It is the first question we would ask.

---

## 5. Risks

| Risk | Impact | Recommended mitigation |
|---|---|---|
| Hardware not certified on the Azure Local catalogue | Unsupported hardware carries no Microsoft support path | Validate all candidate hardware against the catalogue before procurement commitment |
| ToR switches do not support the required DCB capabilities | Storage fabric cannot be built as designed. Affects every site | Confirm switch capability during discovery, before hardware commitment |
| RDMA protocol mismatch between adapters and fabric | Storage network does not function | Confirm installed network card models and select the protocol they support |
| Switchless sites cannot scale through supported paths | A site outgrowing three nodes requires redesign or rebuild | Confirm the three-node ceiling per site during discovery. Design switched where growth is expected |
| Manual storage IP planning across twelve sites | Configuration error at deployment, repeated twelve times | Produce a single addressing standard and apply it identically at every site |
| Twelve remote sites without local IT presence | Deployment and day-two operations do not scale through site visits | Standardise one site configuration, automate deployment, manage through Azure Arc |
| SQL Server business-critical migration | The workloads with the lowest downtime tolerance carry the highest migration risk | Migrate SQL Server in a later wave, after the pattern is proven |
| Hardware lead time on the critical path | Migration cannot start at a location until hardware is delivered and validated. Lead times run to months | Plan backwards from the renewal date. Place orders against the wave plan, not against migration readiness (section 8.1) |
| Manufacturing cutover windows tied to plant shutdowns | A missed window can delay a site by months | Obtain the shutdown calendar for all twelve sites early and build the wave plan around it (section 8.4) |
| Undocumented and unowned workloads in the tail | The final workloads consume disproportionate time and put the renewal date at risk | Identify the tail during discovery and schedule it early with runway (section 8.8) |
| Fifteen locations within an 18-month exit | Approximately one location every five weeks, allowing for a slower start | Wave plan with a pilot site, then parallel waves once repeatable |
| Site-level disaster recovery expectations | Azure Local provides no stretched cluster equivalent to some VMware patterns | Establish the disaster recovery approach early, using replication and Azure services |
| SQL Server host-level licensing across a large cluster | Under unlimited virtualisation, every node a SQL virtual machine can run on requires full Enterprise licensing. Unconstrained placement across 16 nodes multiplies cost | Place SQL Server on a dedicated system with node count sized against the licensing model (section 6.4) |
| Software Assurance lapse under Azure Hybrid Benefit | Loss of the licensing benefit mid-programme, with compliance exposure | Confirm the Software Assurance term and renewal position before relying on the benefit |
| Cutover downtime underestimated | Change windows agreed with manufacturing on optimistic assumptions cannot be met, and a site waits for the next shutdown window | Measure actual cutover duration by workload type during the pilot waves and size later windows on measured data (section 8.5) |
| Legacy BIOS workloads migrate as Generation 1 virtual machines | Generation 1 feature limitations carry forward onto the new platform | Identify firmware type during discovery and plan any required conversion as separate work (section 8.6) |
| Scope ambiguity between 25 sites and 15 identified locations | Deployment count, hardware volume and programme duration could all be understated | Confirm the infrastructure at the remaining 10 sites before hardware sizing (section 4, assumption 8) |
| Regulatory control set not yet defined | Late compliance findings force platform redesign | Identify the applicable control framework during discovery |
| Existing storage platform unknown | Hardware volume, cost case and disposition planning all rest on an undescribed part of the estate. An external array with support life remaining could change the procurement position materially | Establish the storage platform in the first discovery session (section 9 item 11, assumption 9) |
| Stretched cluster assumed available, carried over from VMware | A site-level resiliency design premised on synchronous cross-site clustering is unsupported and must be rebuilt late | State the position in writing at the first design session. Establish the per-tier recovery mechanism early (section 16) |
| Remote sites fall outside the six-month support window | Instance becomes unsupported. At twelve months the Arc Resource Bridge certificates expire and virtual machine functionality breaks | Name an owner for the update cycle, rehearse it against a remote site during the pilot, and fund it as standing operational effort (section 17.2) |
| Sustained WAN loss at a manufacturing site | After 30 days the instance goes out of policy and no new virtual machines can be created, though running workloads continue | Treat WAN resilience at the twelve sites as a continuity requirement. Confirm link redundancy during discovery (sections 3.3, 16.7) |
| Enterprise patching standard mandates a third-party agent | Third-party patching tools are not a supported update path for Azure Local, creating a governance conflict | Raise against Contoso's patching standard during discovery, not at change approval (section 17.1) |
| Application Control blocks Contoso's standard host tooling | Monitoring, backup or security agents fail to run on the platform, discovered at a remote site | Validate the full host tooling set under Enforcement mode during the wave 0 pilot (section 14.4) |
| BitLocker recovery key custody not agreed | Keys escrowed in Active Directory against an OU whose deletion destroys them | Confirm the AD escrow arrangement against Contoso's control set before deployment (sections 12.1, 14.3) |
| Cluster administration assumed to be governed by Entra PIM | Privileged access controls are believed to be in place that do not reach the hosts | Design the on-premises delegation model explicitly and broker elevation through a PAM product (section 12.3) |
| Log Analytics ingestion across fifteen locations | Recurring operational cost absent from the business case, surfacing as an invoice | Size ingestion and retention during design and place it in the business case (section 15.3) |

---

## 6. Licensing and consumption

### 6.1 Base position

Azure Local is licensed as a subscription charged **per physical core per month**, billed through Azure. That charge covers the platform. It does not, on its own, cover the guest operating system licensing for virtual machines running on it.

### 6.2 Azure Hybrid Benefit

Contoso's existing Windows Server position may remove the platform charge entirely.

If Contoso hold **Windows Server Datacenter licences with active Software Assurance**, they are eligible for Azure Hybrid Benefit for Azure Local. One core of Software Assurance enabled Windows Server Datacenter is exchanged for one physical core of Azure Local.

The benefit waives:

- The Azure Local host service fee
- The Windows Server guest subscription

The guest entitlement is significant. Once Azure Hybrid Benefit is active, Contoso can activate **Windows Server subscription** as an add-on at no extra cost, which provides unlimited virtualisation rights for Windows Server guests on the system.

Three conditions apply, and each is a compliance obligation rather than a technicality:

1. **Datacenter edition with active Software Assurance.** Standard edition does not qualify for this benefit.
2. **The guest entitlement requires separate activation.** It is a toggle in the configuration pane, not an automatic consequence of enabling the benefit.
3. **The system may run under Azure Hybrid Benefit only during the Software Assurance term.** On expiry Contoso must renew, disable the benefit, or deprovision the systems using it.

### 6.3 What remains chargeable

Azure Hybrid Benefit waives the platform and Windows Server guest charges. It does not waive:

- Azure services consumed by the platform, including Azure Monitor, Log Analytics ingestion and retention, Microsoft Defender for Cloud, and Azure Backup
- Linux guest operating system licensing and support, where applicable
- SQL Server licensing, which follows its own entitlement rules
- AKS enabled by Azure Arc, where applicable

### 6.4 SQL Server licensing and its effect on the design

SQL Server is licensed separately from Azure Local and follows its own rules. Those rules shape the platform design rather than merely its cost.

Contoso have two licensing models available:

| Model | How it works | Design consequence |
|---|---|---|
| Per virtual core | Licence the virtual cores assigned to each SQL virtual machine, subject to a four core minimum per machine | SQL virtual machines can be placed anywhere. Cost scales with the number of SQL virtual machines |
| Unlimited virtualisation | Licence **all physical cores** on a host with SQL Server Enterprise **plus active Software Assurance**, and run an unlimited number of SQL Server virtual machines on that host | Cost scales with the number of physical cores licensed, not with the number of SQL virtual machines |

The second model carries a material design implication.

Azure Local uses Failover Clustering. Virtual machines move between nodes for maintenance, updates and failure. Under the unlimited virtualisation model, **every node on which a SQL Server virtual machine could run must be fully licensed for SQL Server Enterprise**. On a 16-node system with unconstrained placement, that means licensing 16 nodes of physical cores for SQL Server.

This supports a dedicated SQL Server system rather than SQL Server workloads distributed across a general purpose cluster:

- A dedicated system bounds the number of nodes requiring SQL Server Enterprise licensing
- Node count on that system becomes a licensing decision, sized against SQL Server workload requirements rather than the 16 node ceiling
- General purpose workloads run on separate systems with no SQL Server licensing exposure

We recommend Contoso size the SQL Server system deliberately against the unlimited virtualisation model, and confirm the resulting core count with their licensing specialist before hardware procurement.

**This requires confirmation.** Contoso's entitlement depends on their agreement, their SQL Server edition, and whether Software Assurance is active. The unlimited virtualisation right applies to Enterprise edition with Software Assurance. We recommend Contoso confirm their position with their Microsoft licensing specialist or partner before the SQL Server system is sized.

### 6.5 Information required

Contoso's licensing position determines whether the platform cost is material or close to zero, and it constrains the SQL Server design. We need:

- Current Windows Server edition and licence count
- Whether Software Assurance is active on Windows Server, and its renewal date
- Current SQL Server edition, version and licence count
- Whether Software Assurance is active on SQL Server
- Whether SQL Server is currently licensed per virtual core or under unlimited virtualisation at host level
- The agreement under which those licences are held

---

## 7. Recommended discovery tooling

We recommend Contoso deploy the **Azure Migrate appliance** against the VMware estate at the start of discovery. It answers several of the questions in section 9 with measured data rather than estimates, and the same tooling carries through to migration.

### 7.1 What it provides

| Capability | Value to this programme |
|---|---|
| Automated discovery of the VMware estate | Establishes the real inventory across all 15 locations, rather than working from the stated figure of 300 virtual machines |
| Configuration and performance metadata, collected continuously | Right-sizing based on actual utilisation rather than allocated capacity, which usually reduces the hardware requirement |
| Dependency analysis | Identifies which workloads communicate with which, so migration waves can be grouped without breaking application dependencies |
| Assessment and readiness | Flags workloads that require attention before migration |

### 7.2 It also serves the migration

Microsoft publish a supported path for discovering and replicating VMware virtual machines to Azure Local using Azure Migrate. The appliance deployed for assessment is therefore not throwaway effort: it becomes the migration mechanism, and the discovery output becomes the wave plan.

### 7.3 Relevance to the 18-month timeline

Dependency analysis is frequently omitted from migration planning. With approximately 300 virtual machines across 15 in-scope locations and an 18-month exit, migrating workloads out of sequence risks interrupting applications whose dependencies have not been mapped. The appliance produces this mapping as part of discovery.

We recommend deployment at one datacentre and one manufacturing site first, to establish the pattern and confirm the data quality before extending to all locations.

---

## 8. Migration strategy

### 8.1 The constraint that sets the shape

The VMware renewal falls due in 18 months. We recommend this date is not treated as the migration deadline.

No workload can move to Azure Local at a location until hardware is delivered, racked, cabled, networked and validated there. For 15 locations, **procurement and delivery sit on the critical path ahead of migration**, and hardware lead times for certified Azure Local systems are measured in months, not weeks.

The programme should be planned backwards from the renewal date:

| Milestone | Must complete by |
|---|---|
| Last workload off VMware | Before renewal |
| Last location operational on Azure Local | Before the final migration wave |
| Last hardware delivered and validated | Before that location's wave opens |
| Hardware order placed | Lead time ahead of that date |

We recommend Contoso plan for the estate to be fully migrated in advance of the renewal date, with the final wave completing early enough to absorb overrun.

### 8.2 Disposition before movement

Not every workload on the VMware estate is best placed as a virtual machine on Azure Local. Establishing disposition before sizing avoids procuring capacity for workloads that will not be migrated.

| Disposition | Applies to | Effect |
|---|---|---|
| Retire | Workloads no longer used, or duplicated | Removes hardware requirement entirely |
| Retain temporarily | Workloads tied to hardware or contracts expiring soon | Deferred, not migrated |
| Rehost to Azure Local | The majority. Workloads requiring on-premises residency, latency or plant proximity | The core of the programme |
| Rehost to Azure | Workloads with no on-premises dependency, such as test, development and internet-facing services | Reduces on-premises hardware requirement |
| Replatform | Workloads better served by a managed Azure service than a virtual machine | Reduces long-term operational cost |

Workloads retired or placed in Azure reduce the on-premises hardware requirement. We recommend this exercise is completed against the Azure Migrate inventory described in section 7, before hardware sizing is finalised.

### 8.3 Wave structure

We propose waves defined by risk and repeatability rather than by geography.

| Wave | Scope | Purpose |
|---|---|---|
| 0. Pilot | One datacentre system, low-criticality workloads | Prove the platform, the network design and the migration mechanism. Establish real effort per workload |
| 1. Site pilot | One manufacturing site, complete | Prove the three-node switchless pattern end to end, including remote operations. This pattern repeats eleven times |
| 2. Datacentre general purpose | Non-critical datacentre workloads | Volume migration once the pattern is proven |
| 3. Manufacturing sites | The remaining eleven sites, in parallel batches | The largest deployment effort. Only starts once wave 1 is validated |
| 4. Business critical | ERP and SQL Server, on the dedicated system | Highest risk, migrated last, with the pattern proven and the team experienced |
| 5. Tail | Everything remaining | See 8.8 |

Waves 2 and 3 can run concurrently. They involve different teams, hardware and locations, and running them sequentially extends the programme without corresponding benefit.

### 8.4 Sequencing the manufacturing sites

The twelve manufacturing sites represent the majority of the deployment effort and carry the lowest tolerance for unplanned downtime. We recommend sequencing is determined by production scheduling rather than by geography.

**Sequence by production shutdown calendar.** Manufacturing site workloads support production, so cutover windows are determined by planned plant shutdowns rather than by IT availability. These windows are scheduled well in advance and are difficult to move.

We recommend Contoso provide the shutdown calendar for all twelve sites early in the programme so the wave plan can be built around it. Where two sites share a shutdown window, they are either migrated together or the second waits for the following window.

This is a primary scheduling dependency and should be established at the outset.

### 8.5 Cutover, validation and rollback

Replication is agentless and runs while the source virtual machine remains in service. The outage is confined to the cutover, but it is not zero, and the published guidance is more conservative than is often assumed.

**Microsoft recommend shutting down the source virtual machine before migration**, to ensure no data is lost. The migration wizard offers this as an option. Where Contoso accept that recommendation, downtime per virtual machine comprises:

| Stage | Duration driver |
|---|---|
| Source virtual machine shutdown | Guest operating system and application shutdown time |
| Final delta synchronisation | Volume of data changed since the last replication cycle, and available bandwidth |
| Virtual machine creation and boot on Azure Local | Target platform, generally short |
| Application validation | Defined by the application owner (see below) |

The controllable variable is the final delta. Replicating early and maintaining short synchronisation intervals reduces the change volume at cutover, and therefore the outage. Workloads with high write rates, notably SQL Server, will carry longer final synchronisations and should be scheduled accordingly.

We recommend Contoso measure actual cutover duration during the pilot waves described in section 8.3, per workload type, and use those measured figures to size the change windows for later waves rather than estimating them.

Three points to establish before the first wave:

1. **Validation criteria are defined per workload before its wave opens.** Successful boot is not sufficient evidence of a successful migration. We recommend the application owner defines the acceptance criteria in advance.
2. **The source virtual machine is retained, powered off, until validation is complete.** Rollback depends on the source remaining available, and ceases to be an option once it is decommissioned.
3. **A rollback decision point and decision owner are named for each wave.** Without a named owner, rollback decisions taken during an outage are subject to delay.

### 8.6 Migration throughput constraints

Two published limits affect how the 300 virtual machines are scheduled.

| Constraint | Consequence |
|---|---|
| The Azure portal supports selecting **up to 10 virtual machines at a time** for both replication and migration | The estate is processed in batches of no more than 10. Approximately 300 virtual machines represents at least 30 replication operations and 30 migration operations |
| Migration preserves firmware type: BIOS virtual machines are created as Hyper-V **Generation 1**, UEFI virtual machines as **Generation 2** | Legacy virtual machines carry forward as Generation 1 on Azure Local, which is subject to Generation 1 feature limitations |

The batching limit is an operational planning input rather than a technical obstacle, but it should be reflected in the effort estimate for each wave and in the automation approach.

The firmware conversion warrants attention during discovery. Contoso's older manufacturing workloads are the most likely to be BIOS based, and will therefore migrate as Generation 1 virtual machines. Where a workload requires Generation 2 capability, conversion must be planned as a separate activity rather than assumed to occur during migration.

Secure Boot settings are preserved for UEFI Generation 2 virtual machines.

### 8.7 Source-side prerequisites that gate a workload

A workload is not migratable simply because it is a virtual machine. The following must be established per workload during discovery, because each turns into remediation work with its own lead time:

| Prerequisite | Consequence if unmet |
|---|---|
| **BitLocker must be disabled** on the source virtual machine | The workload cannot be migrated until it is decrypted and re-encrypted afterwards |
| **Encrypted disks are not supported** | Requires a different migration approach for that workload |
| **Shared disks are not supported** | Affects clustered workloads. Needs a redesign, not a migration |
| **VMware Tools installed and the virtual machine powered on** | Discovery and replication will not proceed |
| **Azure Connected Machine agent must be uninstalled** on the source | Migration fails or the machine registers incorrectly |

The BitLocker item is the one to search for first. Contoso's security requirements include BitLocker-based data protection, so it is reasonable to expect a portion of the existing estate is already encrypted, and each such workload carries decryption and re-encryption effort on both sides of the cutover.

### 8.8 The tail

The final workloads in a migration are typically the most difficult: undocumented, without an identified owner, or carrying physical dependencies. They consume disproportionate effort and are a common cause of schedule overrun.

We recommend Contoso identify these workloads during discovery rather than late in the programme. Any workload without an identified owner, without documentation, or carrying a dependency that dependency analysis cannot resolve, should be treated as tail work and scheduled early with deliberate contingency.

### 8.9 Information required

- The VMware renewal date, and whether any extension is negotiable
- Hardware lead times from the preferred vendor for the certified configurations
- The production shutdown calendar for all twelve manufacturing sites
- Application ownership for the 300 virtual machines, and which have no identified owner
- Change control requirements and approval lead time for production manufacturing systems
- The agreed maximum outage window per workload tier, against which cutover is planned
- Firmware type, BIOS or UEFI, across the estate, and any workload requiring Generation 2 capability

---

## 9. Information required

The following change the architecture materially. We have ordered them by the consequence of proceeding without an answer. Items 1, 5 and 7 are answered directly by the Azure Migrate discovery described in section 7.

1. What runs at each of the 12 manufacturing sites, and what stops when a site is offline? This determines node count, resiliency mode and disaster recovery design for 12 of the 15 locations.
2. What network switching exists at the datacentres and the manufacturing sites, and does it meet the requirements in section 3?
3. What is Contoso's Windows Server licensing and Software Assurance position?
4. What is Contoso's hardware position: new procurement, preferred vendor, and whether any existing hardware is Azure Local certified?
5. What are the recovery point and recovery time objectives, by workload tier?
6. Which regulatory frameworks and control sets apply?
7. How are the 300 virtual machines distributed, and what is the split by business criticality?
8. What backup and disaster recovery tooling is in use, and does it support Azure Local?
9. What Azure footprint and governance exist today, including management groups, policy and landing zones?
10. The brief identifies 25 sites but details 15 locations. What infrastructure exists at the remaining 10 sites, and is any of it in scope?
11. What storage platform underpins the VMware estate today: vSAN, an external Fibre Channel or iSCSI array, or local disk? If an external array, what is its remaining support life, and is it a candidate for reuse under the disaggregated deployment model (section 2.1, assumptions 6 and 9)?
12. What are the recovery mechanisms and objectives for each workload tier, and specifically what protects the workloads that are not SQL Server (section 16.3)?
13. What is the WAN resilience at each of the 12 manufacturing sites, given the 30-day connectivity rule (section 16.7)?
14. What is Contoso's enterprise patching standard, and does it mandate a third-party agent on every host (section 17.1)?

---

## 10. Discovery questionnaire

Grouped so that each section can be directed to the appropriate Contoso team. Network questions are set out in section 3 and are not repeated here.

### Workloads and estate

1. How are the 300 virtual machines distributed across the three datacentres and 12 manufacturing sites?
2. Which workloads are business critical, and what downtime is tolerated for each tier?
3. What runs at a manufacturing site, and what stops if that site is offline?
4. What is the split between Windows and Linux, and which Linux distributions are in use?
5. Which SQL Server versions and editions are deployed, and under what licensing arrangement?
6. Do any workloads depend on VMware-specific capabilities such as vSAN, NSX or DRS?
7. Are there virtual machines that cannot be migrated, and what prevents it?
8. Is any manufacturing site expected to grow beyond three nodes of capacity?
8a. What infrastructure exists at the sites outside the 3 datacentres and 12 manufacturing sites, and is any of it in scope for this programme?

### Resiliency and business continuity

9. What are the recovery point and recovery time objectives for each workload tier?
9a. For each workload tier that is not SQL Server, what mechanism is expected to provide site-level recovery?
10. What does site-level disaster recovery mean in Contoso's current environment, and how often is it tested?
10a. Does the current environment rely on a stretched or metropolitan cluster, or on synchronous array replication between sites?
11. Which backup product is in use, with what retention policy and restore testing regime?
12. Is there an existing disaster recovery site, and what is the failover process?

### Infrastructure

13. What is the age and refresh cycle of the current hardware estate?
13a. What storage platform underpins the VMware estate at each datacentre and at the manufacturing sites: vSAN, an external Fibre Channel or iSCSI array, or local disk?
13b. If an external array is in use, what is its make, model and remaining support life, and is it on the Azure Local external storage supported list?
14. Is there a preferred hardware vendor, and is any existing hardware Azure Local certified?
15. Which network card models are installed or proposed, and which RDMA protocol do they support?

### Identity, security and governance

16. What is the current Active Directory topology, and how does it relate to Microsoft Entra ID?
16a. Which organisational unit structure and delegation model should the Azure Local deployment objects follow, given that they cannot be moved after deployment?
16b. Where are BitLocker recovery keys escrowed today, and does Active Directory escrow meet the applicable control set?
16c. Is privileged access to infrastructure brokered through a PAM product today, and which one?
17. Which regulatory frameworks and control sets apply?
18. What privileged access and role-based access control arrangements are in place?
19. What security monitoring exists, and where are logs retained?
19a. Which host-based agents are mandated on every server, and have they been validated to run under Application Control in Enforcement mode?
20. Are there data residency requirements beyond on-premises hosting?
20a. Which Azure management group should the Azure Local instances sit under, and are manufacturing sites and datacentres governed separately?

### Operations

21. Who operates the platform today, how many staff, and at which locations?
22. What is the current patching and update process, and what maintenance windows are available?
22a. Does the enterprise patching standard mandate a third-party patching agent, and can Azure Update Manager be accepted as the update path for this platform?
22b. Who will own the standing update cycle for the twelve remote sites, given the six-month support window?
23. Which monitoring and alerting tools are in use?
23a. What log retention period and immutability requirement applies, and what data volume is expected per location?
24. What does change control require for production manufacturing systems?
25. What Azure governance exists today, including management groups, policy assignments and landing zones?

### Commercial and timeline

26. On what date does the VMware licensing renewal fall due?
27. What is the Windows Server licensing and Software Assurance position?
28. Is SQL Server licensed per virtual core, or under unlimited virtualisation at host level with Enterprise edition and Software Assurance?
29. What is the budget position between capital and operational expenditure?
30. Is there an existing Azure agreement, and what commitment does it carry?

---

## 11. Recommended approach

We recommend Contoso run discovery in two tracks. The datacentre estate and the manufacturing sites involve different stakeholders and different design decisions. A combined workshop tends to be dominated by the datacentre discussion, leaving the twelve sites that carry most of the deployment effort under-examined.

We further recommend a pilot deployment at one manufacturing site early in the programme. The remaining eleven sites depend on a repeatable pattern. A pilot proves that pattern, establishes the real deployment effort per site, and produces evidence for the business case ahead of the renewal date.

---

## 12. Identity and access

Contoso run an Active Directory integrated environment with centralised operations and security teams. Azure Local fits that model, but it introduces a second identity plane in Azure, and the two do not overlap as neatly as is usually assumed.

### 12.1 Active Directory is a prerequisite, not a migration step

The standard Azure Local deployment is domain joined, and Active Directory must be prepared before deployment rather than during it. The preparation produces:

- A **dedicated organisational unit** holding all deployment objects, specified as a distinguished name
- **Group policy inheritance blocked** on that OU
- A **user account with all rights to the OU**, used by Lifecycle Manager

Two consequences are permanent and catch programmes out:

1. **Computer objects cannot be moved to a different OU after deployment.** The OU structure is a design decision taken once, before the first node is deployed, and it must fit Contoso's existing delegation model.
2. **Deleting the OU deletes the BitLocker recovery keys stored against it.** See section 14.3.

The deployment account carries specific rules: the username is 1 to 20 characters using only letters, numbers, hyphens and underscores; it cannot be `admin`; it cannot be identical to the local administrator account; and it must be unique per Azure Local instance. The password must be at least 14 characters with lower case, upper case, a numeral and a special character. Local administrator credentials must be **identical across every machine** in a system.

For fifteen locations this is fifteen unique lifecycle accounts, and a credential standard that has to survive the departure of whoever set it up.

### 12.2 The AD-less option

Azure Local supports deployment using **local identity with Azure Key Vault**, generally available from version 2604, for systems that are not domain joined. This is worth knowing about but we do **not** recommend it for Contoso: the manufacturing workloads are Active Directory integrated, and an AD-less platform hosting domain-joined guests solves nothing while removing a management path the operations team already knows.

It is not an Entra ID joined deployment, and should not be described as one.

### 12.3 Two planes of administration, and the gap between them

This is the design point that matters most for a centralised security team.

Azure role-based access control governs the **Azure projection** of the system: the Arc-enabled resource, its resource group, and Azure management actions against it. It does **not** flow down into Hyper-V, Failover Clustering, storage, Windows Admin Center or out-of-band hardware management. Those remain governed by on-premises Active Directory groups.

The practical consequences:

- **Microsoft Entra Privileged Identity Management does not govern cluster administration.** It governs Azure roles and Entra directory roles. An administrator holding cluster rights through an AD group is outside its reach entirely.
- **There is no native Entra multifactor challenge** for an administrator authenticating to the cluster, to Windows Admin Center, or to the out-of-band controller. Those use an AD or local credential.
- Time-bound elevation on the on-premises path requires a **privileged access management product brokering the credential**, or a hardened jump host model. It is not a platform feature.
- The Azure landing zone RBAC model must be **mirrored** on the on-premises side, deliberately, rather than assumed to be inherited.

| Entry point | Access control | Multifactor mechanism |
|---|---|---|
| Azure portal and Arc management | Azure RBAC, Entra ID | Conditional Access |
| Windows Admin Center | AD credential | Depends on gateway configuration. Confirm |
| Cluster, host, PowerShell, RDP | On-premises AD groups | PAM brokered. Not native |
| Out-of-band controller | Local or directory integrated | Confirm OEM capability |

### 12.4 Built-in roles

The built-in roles remain branded **Azure Stack HCI** in the portal, which is a naming legacy rather than a different product. A design document that invents plausible-sounding names such as "Azure Local Administrator" will not match what Contoso's team sees:

| Role | Purpose | Assign at |
|---|---|---|
| Azure Stack HCI Administrator | Platform administration | Subscription or resource group |
| Azure Stack HCI VM Contributor | Create and manage Azure Local virtual machines | Resource group or resource |
| Azure Stack HCI VM Reader | Read-only virtual machine access | Resource group or resource |
| Azure Connected Machine Onboarding | Arc registration only. Cannot manage extensions or delete servers | Resource group. Service principal only |
| Azure Connected Machine Resource Administrator | Full Arc server management, including extensions | Resource group |

Deployment additionally requires Key Vault roles (Key Vault Data Access Administrator, Key Vault Secrets Officer, Key Vault Contributor) and Storage Account Contributor, plus User Access Administrator and Contributor on the subscription.

### 12.5 Arc extensions are an administrative boundary, not a monitoring feature

Scoping Azure RBAC does not wall off "infrastructure" from "operating system". Anyone holding Contributor or Azure Connected Machine Resource Administrator on an Arc-enabled machine is **effectively an operating system administrator**, because they can deploy an extension that runs arbitrary code as Local System.

Where Contoso's security team requires that separation, it is enforced agent side rather than by role assignment:

- An **extension allow list** on the agent, preferring an explicit allow list so anything new is denied by default
- **Agent monitor mode**, which restricts the agent to monitoring and security extensions and disables guest configuration

Azure Policy can restrict extensions centrally, but anyone able to edit policy assignments can undo it. It is a control, not a boundary.

---

## 13. Azure Arc and Azure connectivity

### 13.1 What Arc actually provides

Each node is Arc registered through the Azure Connected Machine agent during deployment, and the deployment automatically enables the Arc Resource Bridge and the supporting infrastructure. From that point Azure is the control plane: deployment, updates, virtual machine lifecycle, monitoring, policy and role assignment are all driven from Azure against an on-premises system.

Arc virtual machine management depends on the Arc Resource Bridge, a **named custom location**, logical networks and virtual machine images. The custom location name should be reserved and standardised up front, because it appears in every subsequent reference to the system.

Arc control plane connectivity itself is free. The charges arise from the services consumed through it, which are set out in section 6.3 and section 15.3.

### 13.2 Connectivity constraints

These apply to every location and should be reflected in the firewall change requests described in section 3.3.

| Constraint | Design consequence |
|---|---|
| Outbound ports **80 and 443** both required | Port 443 alone does not meet the requirement |
| **HTTPS inspection is not supported** anywhere on the path | Break and inspect must be disabled end to end. This also precludes Entra ID tenant restrictions version 1 |
| **Azure Arc Private Link Scopes are not supported by Azure Local** | The Arc endpoints must always resolve to public addresses. Note the distinction: Arc-enabled *servers* do support Private Link Scope. Azure Local does not |
| PaaS private endpoints **are** supported | Storage, Key Vault and similar services can use private endpoints, routed over ExpressRoute or site to site VPN |
| Azure Local instances are created only in **supported control plane regions** | Currently East US, West Europe, Australia East, Southeast Asia, India Central, Canada Central, Japan East, South Central US, and US Gov Virginia. Validate against the current list at build time. This list changes |

The control plane region carries only cluster metadata, telemetry and update state. Virtual machine data and Storage Spaces Direct data remain on the local system, which is the answer to the data residency requirement in section 1.

### 13.3 Arc gateway

The Arc gateway substantially reduces the endpoint allow list, and therefore the size of the firewall change request across fifteen locations. Four constraints determine whether Contoso can use it:

- Available on **new deployments** of version **2506 and later**
- Generally available for Azure Local infrastructure and Azure Local virtual machines. **Preview** for AKS on Azure Local
- **Does not carry HTTP traffic**, so HTTP endpoints still require separate allowance
- **Does not support TLS terminating proxies**, and **cannot be enabled after deployment**

The last point is the decision-forcing one. If Contoso want the gateway, it has to be settled before the first site is deployed, not adopted later once the firewall burden becomes apparent.

### 13.4 Disconnected operations

Disconnected operations allow deployment and management without a connection to the Azure public cloud, from version 2602. We do **not** propose it for Contoso, and record it here only to close the question: it requires an eligible agreement, a Standard or higher support plan, a validated business need, Premier Solutions hardware and a **dedicated management cluster**. It is operationally heavier, and Contoso's sites have wide area connectivity.

The relevant control for Contoso's remote sites is the 30-day sync rule in section 3.3, not disconnected operations.

---

## 14. Security

Contoso's stated security requirements are BitLocker-based data protection, RBAC and least privilege, regulatory compliance controls, and security monitoring with auditability. Azure Local addresses most of this in the platform rather than through added product, which is a genuine differentiator against a self-assembled alternative.

### 14.1 Hardware root of trust

Every node requires **TPM 2.0 present and enabled**, and **Secure Boot present and enabled**. Hardware virtualisation must be enabled in firmware. These are deployment prerequisites, not hardening options, and they are a procurement checklist item rather than something to discover during deployment.

### 14.2 The security baseline and drift control

Azure Local applies a security baseline at deployment with **more than 300 security settings enabled from the start**, aligned to CIS Benchmark and DISA STIG requirements.

The part worth drawing attention to is drift control: with it applied, **security settings are refreshed every 90 minutes** and any deviation from the desired state is remediated. For twelve manufacturing sites with no local IT presence, a platform that re-asserts its own security posture every ninety minutes is a materially different operational proposition from one that requires someone to notice.

Baseline compliance is expected at approximately 99 percent. The known non-compliant rule is **minimum password length**, which defaults to 7 and must be set by the customer. Contoso should set it to 14 to match the deployment account requirement in section 12.1.

Features configurable at deployment time: security baseline, Credential Guard, Application Control, BitLocker for the operating system boot volume, BitLocker for data volumes, SMB signing for external traffic, and SMB encryption for in-cluster traffic.

### 14.3 Data at rest and key custody

**Data-at-rest encryption is enabled on data volumes created during deployment**, covering both infrastructure volumes and workload volumes.

Key custody is where designs are usually vague, and it differs by deployment type:

| Key protector | Where it goes |
|---|---|
| Recovery password | **Active Directory** for a domain joined deployment. **Azure Key Vault** for a non-domain joined deployment |
| External key | Stored at `C:\Windows\Cluster` on the owner node |

Because we propose a domain joined deployment, **Contoso's BitLocker recovery keys land in Active Directory, not Key Vault**. Microsoft's guidance is that recovery keys must be stored in a secure location outside the system. Two actions follow: Contoso confirm the AD escrow arrangement meets their control set, and the OU deletion risk in section 12.1 is understood by whoever administers the directory.

**Azure Key Vault is required at deployment** regardless, to store cryptographic keys, local administrator credentials and BitLocker recovery keys generated during deployment. Public network access must be enabled on that key vault.

A complete design should state encryption at each layer separately: BitLocker on cluster shared volumes, guest-level encryption such as Transparent Data Encryption for SQL Server, and encryption of the backup target.

### 14.4 Application control

**Application Control is enabled by default** and limits which applications and code can run on the core platform. It ships signed base policies for both Enforcement and Audit mode, and Microsoft recommend running in **Enforcement** mode.

This is a change Contoso's operations team must understand before the pilot, not during it. Any third-party agent, monitoring tool or backup component installed on the host is subject to it. The pilot in wave 0 should specifically validate that Contoso's standard host tooling runs under Enforcement.

Microsoft Defender Antivirus is enabled and configured by default.

### 14.5 Microsoft Defender for Cloud

Foundational cloud security posture management is free and applies to Arc-enabled resources, providing Secure Score, recommendations against the Microsoft Cloud Security Benchmark, and asset inventory. **Arc-enabled machines become assessed resources as soon as they onboard**, whether or not a paid plan is enabled. Contoso should expect a Secure Score movement when fifteen locations onboard, and should separate that from unrelated benchmark changes.

Defender for Servers adds security alerts and endpoint detection, and **carries a per-node cost**. Two points of caution:

- Defender for Cloud on Azure Local is currently documented as **preview**. It should be presented to Contoso as a direction of travel, not as a committed control.
- Onboarding a machine to Arc does **not** by itself enable Defender for Servers. It is enabled by the plan being active on the subscription, or by an Azure Policy deploy-if-not-exists assignment in scope.

### 14.6 Transport and certificates

TLS 1.2 is the floor rather than an answer. The design should state, per management endpoint, which accept an enterprise-issued certificate and which ship with self-signed certificates that cannot be replaced, with a compensating control where an endpoint cannot take an enterprise certificate. Out-of-band management should sit on a dedicated VLAN, separate from management and data networks.

---

## 15. Governance

### 15.1 Where Azure governance applies, and where it stops

Azure Local surfaces in Azure as an Arc-enabled resource inside a subscription. Management group inherited policy and RBAC apply to **that object and its Arc-enabled resources**. As set out in section 12.3, they do not reach Hyper-V, cluster, storage or out-of-band permissions.

A governance design for Contoso therefore has two halves that must be kept deliberately consistent: the Azure landing zone placement of fifteen instances, and the on-premises Active Directory delegation model that actually controls the hosts.

### 15.2 Azure Policy

Azure Policy and machine configuration apply to Azure Local and its Arc-enabled machines. The concrete, documented use is the built-in policy **Windows machines should meet requirements of the Azure compute security baseline**, which produces a compliance report against the Azure Local hosts and gives Contoso's compliance team a reportable position without additional tooling. Insights can also be enabled at scale through Azure Policy, which is the practical way to onboard fifteen locations consistently.

Contoso should decide before the pilot:

- Which management group the Azure Local instances sit under, and whether manufacturing sites and datacentres are separated
- The tagging standard applied to each instance, covering location, wave, environment and cost centre
- Which policies are audit and which are deny, given that a deny assignment can block a deployment at a remote site with nobody present

### 15.3 Monitoring, logging and what it costs

Insights collects data using the **Azure Monitor Agent** and stores it in a **Log Analytics workspace**, covering nodes, virtual machines and storage, including CPU, memory, network and storage IOPS, throughput and latency.

The cost model needs stating plainly, because it is the line customers are surprised by:

| Capability | Cost |
|---|---|
| Metrics, available out of the box | No additional cost |
| Health alerts | No additional cost |
| Insights via Log Analytics | **Chargeable** on data ingested and retention. First 5 GB per billing account per month is free |
| Defender for Servers | **Chargeable** per node |

Fifteen locations ingesting continuously is a real operational expenditure line, and it belongs in the business case rather than in the first invoice. Log Analytics supports immutable retention settings, which meets part of an audit requirement natively.

### 15.4 The support boundary

Certified hardware means a joint support model, and a design pack should say who Contoso calls first for a platform incident and how an OEM and Microsoft case is escalated jointly. This is an unglamorous question that becomes urgent at 02:00 at a manufacturing site.

---

## 16. Business continuity and disaster recovery

Contoso's stated resiliency requirements are cluster-level high availability, site-level disaster recovery for critical workloads, backup and recovery, and defined RPO and RTO objectives. The first is delivered by the platform. The second requires a decision that Azure Local constrains more tightly than VMware does, and it should be taken early.

### 16.1 Stretched clusters are not available

This is the single most important thing to establish with Contoso, because it is the assumption most likely to be carried over from the VMware estate.

**Stretched clusters are not supported in Azure Local.** Azure Stack HCI 22H2 supported stretched clustering using Storage Replica; the current Azure Local release does not, and Microsoft state the position explicitly. Any design premised on a metropolitan pair of sites replicating synchronously, in the manner of a VMware metro cluster backed by array replication, is unsupported.

Two further facts close off the workarounds:

- **Storage traffic is SMB, layer 2 and not routable.** A stretched storage fabric between sites is a non-starter independently of the cluster mode question.
- Storage adapters are single purpose. Traffic requiring north-south communication cannot use them.

We recommend this is said to Contoso plainly, early, and in writing. Discovering it during design costs credibility; discovering it during deployment costs the programme.

### 16.2 What is available instead

**Rack aware clustering**, generally available from version 2601, provides fault domain awareness across two racks, each functioning as a **local availability zone**, with a single storage pool. It scales 2+2, 3+3 and 4+4, which is the source of the 8-node ceiling in section 2.1.

It is bounded by **latency, not by building**: the required round-trip latency between racks is **1 ms or less**, and the racks may be in two different rooms or buildings. It is therefore a campus-level construct, not a metropolitan disaster recovery answer, and it is **not supported with external SAN storage** in hyperconverged deployments.

For Contoso's three datacentres, rack aware clustering is worth evaluating where two rooms exist within the latency budget. It does not substitute for cross-site disaster recovery.

### 16.3 Cross-site disaster recovery

With stretched clustering unavailable, site-level recovery is assembled from:

| Mechanism | What it covers | Position |
|---|---|---|
| **Azure Site Recovery** | Continuous replication of virtual machines **from Azure Local to Azure**, with failover and failback | Supported. Note the direction: this is a recovery-into-Azure story, not on-premises site to site |
| **Application-native replication** | SQL Server Always On availability groups, and equivalents | The strongest option for the workloads that matter most. Recommended for the business-critical ERP and SQL Server estate |
| **Azure Backup Server (MABS) v3 UR2** | Azure Local host system state and bare metal recovery, and virtual machines running on the system | The documented first-party backup path |
| Third-party backup and replication | Varies | Supported in principle. Product must be validated against Azure Local |

**SQL Server Always On is the answer for SQL Server. The design question is everything that is not SQL Server.** That is where the specification currently has to stop, because it depends on Contoso's recovery objectives.

### 16.4 Refusing a blanket RPO and RTO

We do not propose platform-wide recovery objectives, and we recommend Contoso treat any supplier who offers them without a workload tier as a warning sign. The recovery objective is a property of the mechanism protecting a given workload, not of the platform.

The deliverable is a **per-tier table**, produced during discovery, naming for each workload tier the protecting mechanism and the RPO and RTO that mechanism actually delivers. Section 9 item 5 and section 10 question 9 collect the inputs.

One consistency check to apply to Contoso's own stated requirements: a very high availability target and a workload tier with no defined recovery mechanism cannot both be true. Where the current environment carries that inconsistency, it should be surfaced rather than carried forward.

### 16.5 In-system resiliency

Within a system, Failover Clustering, Storage Spaces Direct resiliency and live migration provide node-level availability.

| Nodes | Recommended resiliency | Storage efficiency | Failures tolerated |
|---|---|---|---|
| 2 | Nested resiliency, recommended for production | 25 percent nested two-way mirror, roughly 35 to 40 percent nested mirror-accelerated parity | Two hardware failures |
| 2 | Two-way mirror | 50 percent | One hardware failure |
| 3 | Three-way mirror | 33.3 percent | Two hardware failures |
| 4 and above | Three-way mirror, or dual parity for capacity workloads | 33.3 percent mirrored. Dual parity from 50 percent at four nodes up to 80 percent | Two hardware failures |

At the manufacturing sites the three-node three-way mirror gives **33.3 percent storage efficiency**, so raw capacity must be planned at roughly three times usable. This is the figure most often missed in early sizing, and across twelve sites it is a material hardware number.

Two qualifications on any resiliency claim:

1. Tolerating two failures does not mean tolerating the loss of two-thirds of capacity. The behaviour that matters is what happens on a **second concurrent failure before rebuild completes**, and how long that rebuild window is.
2. Rebuild time should be measured during the pilot, not estimated.

### 16.6 Witness and quorum

| Nodes | Witness |
|---|---|
| 2 | **Required** |
| 3 to 4 | **Strongly recommended** |
| 5 and above | Not needed |

A disk witness is not supported with Storage Spaces Direct. A cloud witness requires an Azure Storage account, and **the same storage account cannot be used for multiple systems**, which for Contoso means a distinct storage account per site.

At the three-node manufacturing sites the witness is strongly recommended, and its availability depends on the same wide area link as the 30-day sync rule. Where a site's WAN resilience is weak, a file share witness should be considered instead.

### 16.7 Connectivity as a continuity concern

Section 3.3 records the 30-day sync rule. It belongs here as well, because at a manufacturing site the failure mode is a business continuity one: the plant keeps running, but the platform cannot accept change until connectivity returns. Contoso should treat WAN resilience at the twelve sites as a continuity requirement, not only a performance one.

---

## 17. Operations and lifecycle

Contoso's driver is reduced operational complexity across 25 sites with centralised teams. This section sets out what that actually looks like, including the constraints that bind hardest at remote sites.

### 17.1 The update mechanism

A **solution update** covers the operating system, core agents and services, and the solution extension, which carries the OEM drivers, firmware and partner content. The Azure Connected Machine agent and the Arc Resource Bridge and its dependencies update automatically.

Updates are driven from **Azure Update Manager** in the portal, or from PowerShell. This is a single mechanism across all fifteen locations, driven centrally, which is precisely the operational simplification Contoso are asking for.

The supported interface list is narrow, and the exclusions matter because they are what Contoso's team may be used to:

**Not supported for updating Azure Local:** SConfig, Windows Admin Center, Azure Update Manager from the Machines pane, the Updates pane on the machine resource page, manual runs of Cluster-Aware Updating, and any third-party patching tool.

That last exclusion should be checked against Contoso's existing enterprise patching standard early. A mandated third-party patching agent is a governance conflict, not a technical one, and it is better raised in discovery than in a change advisory board.

### 17.2 The support window is six months, and it is not negotiable by neglect

Azure Local follows the **Modern Lifecycle policy**. To remain supported, an instance must **stay within six months of the most recent release**. Each release is supported for six months. Versions not updated within six months are no longer supported, and support requests are then available only for patching back to a supported release.

There is a second, harder ceiling: **the Arc Resource Bridge requires solution updates to be applied within one year**, or its certificates expire and Azure Local virtual machine functionality breaks.

Release cadence is monthly cumulative updates, semi-annual feature updates, plus hotfixes and solution builder extension updates as needed.

For Contoso this converts an operational preference into a programme requirement. **Twelve remote sites with no local IT presence must be patched at least twice a year, from Azure, or they fall out of support and eventually break.** The update mechanism is centralised and this is achievable, but it must be designed as a standing operational commitment with named ownership, not left to be discovered when a site goes unsupported. It also belongs in the business case, because it is ongoing effort rather than a migration cost.

We recommend the pilot in wave 0 explicitly rehearses an update cycle, including a remote site, before wave 3 commits eleven more.

### 17.3 Scale operations

| Operation | Position |
|---|---|
| Add a node | Supported, **one node at a time**, up to the 16-node maximum. Portal-based add-node is currently **preview** |
| Remove a node | **It is not possible to permanently remove a node from a system** |
| Scale out, single node to two nodes | Supported with and without a switch |
| Scale out, two nodes to three nodes | **Switched storage only** |
| Scale out, three nodes to N nodes | **Switched storage only** |

Two implications for the design in section 2:

1. **The storage switchless manufacturing sites cannot grow.** The scale-out path beyond two nodes requires a switched storage fabric, which the switchless sites do not have, and portal or ARM scale-out is unsupported on switchless deployments regardless. Growth at a site means a redesign, not an expansion. Assumption 3 in section 4 is therefore load bearing and must be confirmed.
2. **Capacity cannot be reclaimed by removing nodes.** Sizing errors are corrected by adding, not by shrinking.

Adding a node requires the lifecycle account to be active with unchanged credentials, which ties back to the credential standard in section 12.1. The new node is validated against CPU and memory, producing a warning on mismatch, and against drives, producing a blocking error. Storage pool rebalance after an addition can run for multiple days.

### 17.4 Windows Admin Center

Windows Admin Center remains available for day-to-day on-premises management alongside PowerShell, Hyper-V Manager and Failover Cluster Manager. Its role has narrowed: from 23H2 its extensions are no longer supported for installing drivers and firmware, and it is not a supported update interface.

Contoso should plan on Azure as the primary management surface, with Windows Admin Center as a local tool rather than the operational centre of gravity.

### 17.5 Deployment tooling

The **Environment Checker** validates networking, Active Directory and hardware compatibility, and runs stand-alone before procurement. Given that hardware sits on the critical path (section 8.1) and that TLS inspection breaks deployment silently (section 3.3), we recommend it is run at a representative datacentre and a representative manufacturing site before any hardware order is placed.

---

## 18. Architecture trade-offs

Sections 4 and 5 record what we do not know and what could go wrong. This section records what we have deliberately given up, and why. Every position in this specification buys something at the expense of something else, and a design that presents only its advantages has not been reviewed.

The framing follows the [Azure Well-Architected Framework service guide for Azure Local](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-local), which names two trade-offs directly: redundancy increases cost, and scalability without effective workload planning increases cost. Both apply to Contoso, and three more arise from the specific shape of this estate.

### 18.1 Redundancy against cost

**What we chose.** Three-way mirror everywhere: at the datacentre systems above four nodes, and at all twelve three-node manufacturing sites. N+1 capacity reservation as the minimum, N+2 on the SQL Server system.

**What it costs.** Three-way mirror lands at roughly **33% usable capacity**. Contoso buy three terabytes of raw disk for every usable terabyte. Reserving a further machine's worth of capacity per system for N+1 takes more off the top again, and the WAF guidance to leave 5% to 10% of the pool unallocated for in-place repair takes a little more. On a 300-VM estate spread across fifteen locations, that multiplier is the single largest line in the hardware case.

**Why we accepted it.** Two-way mirror survives one failure and gives 50% efficiency, but on a three-node site a second concurrent fault is unrecoverable, and these are production manufacturing sites with no local IT presence (assumption 2, risk register). Parity is cheaper again and materially slower on write, which rules it out for the SQL Server and line-of-business workloads. The WAF position is that a lower RTO and RPO costs money and demands operational rigour; Contoso's stated requirement to maintain existing SLAs through the migration is what buys the mirror.

**What would change it.** If any manufacturing site turns out to run non-production or reconstructable workloads only, that site can drop to a cheaper resiliency type. Section 9 does not currently ask the question. It should.

### 18.2 Scale-out against up-front capacity planning

**What we chose.** Storage switchless at three nodes for the twelve manufacturing sites.

**What it costs.** Section 2.4 records the constraint and it is worth restating as a trade-off rather than a caveat: a storage switchless instance **cannot be scaled out through the portal or ARM**, and the pattern supports four nodes at most. A site that outgrows three nodes is a rebuild, not an expansion. We have traded the ability to grow a site for the removal of twenty-four storage switches from sites with nobody to maintain them.

**Why we accepted it.** Assumption 3 says the sites will not exceed three nodes within the life of the platform. That assumption is doing a great deal of load-bearing work, and it is unconfirmed.

**What it costs if the assumption is wrong.** A rebuild at a production manufacturing site, scheduled against a plant shutdown window that may be months out (risk register, section 8.4). This is the most expensive way for an assumption in this document to fail.

**The counter-position.** At three nodes with dual link, each node carries four RDMA cards. Section 2.4 already notes that the adapter cost can exceed the switch cost at that node count. So the switchless design may not even be the cheaper option on capital, and its saving is really operational: fewer devices to configure, patch and fail at a site with no engineer. State it that way to Contoso rather than as a hardware saving, because on a per-site bill of materials it may not survive scrutiny.

### 18.3 Blast radius against consolidation efficiency

**What we chose.** Multiple systems per datacentre, split by workload lifecycle, maintenance window and licensing boundary, rather than one large system approaching the 16-node ceiling.

**What it costs.** Every additional system carries its own infrastructure volumes, its own N+1 reservation, its own quorum and its own update cycle. Four systems of four nodes reserve four machines' worth of capacity; one system of sixteen reserves one. Consolidation is measurably cheaper on both capital and operational effort.

**Why we accepted it.** Three reasons, and the third is decisive. Blast radius: one system failing takes a defined set of workloads with it rather than a datacentre. Maintenance: updates drain nodes one at a time and temporarily reduce cluster resiliency, so separating workloads by acceptable maintenance window means the SQL Server estate is not being drained on the same night as ERP. And licensing: under SQL Server unlimited virtualisation every node a SQL VM *could* run on requires full Enterprise licensing, so unconstrained placement across sixteen nodes multiplies the licence count (section 6.4, risk register). The licensing boundary is not a design preference, it is arithmetic.

**Where the balance sits.** This trade-off should be re-run once Azure Migrate produces real workload data. The right number of systems per datacentre is an output of discovery, not a position to fix now.

### 18.4 Site-level recovery against platform simplicity

**What we chose.** Replication and Azure services for site-level disaster recovery, per section 16.

**What it costs.** Contoso do not get what a VMware metropolitan cluster gave them. Azure Local has no stretched cluster equivalent, and no synchronous cross-site storage replication to build one on. Recovery moves up the stack into each workload: SQL Server Always On for the databases, Azure Site Recovery or a backup-and-restore path for the rest. That is more moving parts, per tier, with per-tier recovery objectives to define and test, rather than one platform-level capability that covered everything.

**Why we accepted it.** There is no alternative to accept it against. This is a platform constraint, not a design choice, and the trade-off Contoso are really making is at the VMware exit decision rather than here.

**Why it belongs in this section anyway.** Because it is the position most likely to be assumed away. The risk register carries it twice, and next step 4 asks for it to be stated in writing before design proceeds. A stakeholder who believes a stretched cluster is coming will not discover otherwise until the design review, and by then the recovery design has to be rebuilt.

### 18.5 Standardisation against per-site optimisation

**What we chose.** One site configuration, applied identically at all twelve manufacturing sites, with a single generated storage addressing standard (section 2.5).

**What it costs.** No site gets a design tuned to its actual workload. A site running four VMs gets the same three-node build as a site running forty. On the small sites that is straightforward overspend.

**Why we accepted it.** Seventy-two storage subnets planned by hand across twelve sites, with no local IT presence at any of them, is a defect factory. The operational cost of twelve variants exceeds the hardware saving of tuning each one, and standardisation is what makes remote Arc-based operations tractable at all. This is the same reasoning that produced the wave plan in section 8: repeatability is the scarce resource in a fifteen-location programme inside eighteen months.

**What would change it.** Azure Migrate output showing a genuine bimodal split in site size. If four sites are materially smaller than the rest, two standards may beat one. Two. Not twelve.

### 18.6 Summary

| Trade-off | Given up | Gained | Confirm during discovery |
|---|---|---|---|
| Three-way mirror and N+1 | ~67% of raw capacity | Node-fault tolerance at every site, SLA continuity | Whether any site is non-production (section 9) |
| Storage switchless at the sites | Supported scale-out path, four-node ceiling | Twenty-four fewer switches to operate remotely | Assumption 3, the three-node ceiling per site |
| Multiple systems per datacentre | Consolidation efficiency, reserved capacity | Contained blast radius, separable maintenance, bounded SQL licensing | Workload profile from Azure Migrate |
| Replication-based site recovery | A single platform-level DR capability | The only supported path available | Per-tier RPO and RTO table (next step 10) |
| One standard site build | Per-site right-sizing | Repeatability, remote operability, fewer defects | Site size distribution from Azure Migrate |

Three of the five rest on data Contoso have not yet provided. That is the honest state of the design, and it is why section 11 recommends discovery before detailed design rather than after.

---

## 19. References

All positions in this specification are sourced from Microsoft Learn. Documentation is versioned per release train, and the citations below reflect the **azloc-2608** view as at 19 August 2026. Version-specific claims should be revalidated against the current release before customer delivery.

| Topic | Reference |
|---|---|
| System requirements, maximum specifications, control plane regions | https://learn.microsoft.com/en-us/azure/azure-local/concepts/system-requirements-23h2 |
| Scalability and deployment models, node ceilings | https://learn.microsoft.com/en-us/azure/azure-local/scalability-deployments |
| Network reference patterns overview, storage switchless considerations | https://learn.microsoft.com/en-us/azure/azure-local/plan/network-patterns-overview |
| Three-node storage switchless, dual ToR, dual link pattern | https://learn.microsoft.com/en-us/azure/azure-local/plan/three-node-switchless-two-switches-two-links |
| Firewall requirements, ports, HTTPS inspection, Arc Private Link | https://learn.microsoft.com/en-us/azure/azure-local/concepts/firewall-requirements |
| Arc gateway overview | https://learn.microsoft.com/en-us/azure/azure-local/deploy/deployment-azure-arc-gateway-overview |
| Connectivity and the 30-day sync rule | https://learn.microsoft.com/en-us/azure/azure-local/faq |
| Active Directory preparation | https://learn.microsoft.com/en-us/azure/azure-local/deploy/deployment-prep-active-directory |
| Deployment prerequisites, Key Vault, local administrator credentials | https://learn.microsoft.com/en-us/azure/azure-local/deploy/deployment-prerequisites |
| Registration and deployment permissions | https://learn.microsoft.com/en-us/azure/azure-local/deploy/deployment-arc-register-server-permissions |
| Built-in RBAC roles for virtual machine management | https://learn.microsoft.com/en-us/azure/azure-local/manage/assign-vm-rbac-roles |
| Security features, baseline, Application Control, Defender | https://learn.microsoft.com/en-us/azure/azure-local/concepts/security-features |
| Managing the security baseline and drift control | https://learn.microsoft.com/en-us/azure/azure-local/manage/manage-secure-baseline |
| BitLocker and key management | https://learn.microsoft.com/en-us/azure/azure-local/manage/manage-bitlocker |
| External SAN storage support | https://learn.microsoft.com/en-us/azure/azure-local/concepts/external-storage-support |
| Rack aware clustering | https://learn.microsoft.com/en-us/azure/azure-local/concepts/rack-aware-cluster-overview |
| Stretched clusters, unsupported. Archived 22H2 page carrying the statement | https://learn.microsoft.com/en-us/previous-versions/azure/azure-local/concepts/stretched-clusters |
| Hybrid capabilities, Azure Site Recovery, Azure Backup Server | https://learn.microsoft.com/en-us/azure/azure-local/hybrid-capabilities-with-azure-services-23h2 |
| Storage resiliency and efficiency by node count | https://learn.microsoft.com/en-us/windows-server/storage/storage-spaces/plan-volumes |
| Quorum and witness requirements | https://learn.microsoft.com/en-us/windows-server/storage/storage-spaces/quorum |
| Updates, solution updates, supported interfaces, lifecycle policy | https://learn.microsoft.com/en-us/azure/azure-local/update/about-updates-23h2 |
| Release information and support window | https://learn.microsoft.com/en-us/azure/azure-local/release-information-23h2 |
| Adding a node, scale-out matrix | https://learn.microsoft.com/en-us/azure/azure-local/manage/add-server |
| Monitoring, Insights, Azure Monitor Agent, billing | https://learn.microsoft.com/en-us/azure/azure-local/manage/monitor-single-23h2 |
| Disconnected operations | https://learn.microsoft.com/en-us/azure/azure-local/manage/disconnected-operations-overview |
| VMware migration overview and requirements | https://learn.microsoft.com/en-us/azure/azure-local/migrate/migration-azure-migrate-vmware-overview |
| VMware migration prerequisites, firmware and generation behaviour | https://learn.microsoft.com/en-us/azure/azure-local/migrate/migrate-vmware-requirements |
| Azure Local catalogue, certified hardware | https://aka.ms/azurelocalcatalog |
| Well-Architected Framework service guide, pillar checklists and trade-offs | https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-local |
| Azure Local baseline reference architecture | https://learn.microsoft.com/en-us/azure/architecture/hybrid/azure-stack-hci-baseline |

---

## Next steps

1. Contoso confirm or correct the assumptions in section 4.
2. Contoso provide the network information in section 3 and the information required in section 9.
3. Contoso confirm the Windows Server and SQL Server licensing position in section 6.5.
4. Microsoft confirm the stretched cluster position in section 16.1 with Contoso in writing, before design proceeds.
5. Contoso confirm the Active Directory organisational unit and delegation design in section 12.1, which cannot be changed after deployment.
6. Contoso decide whether the Arc gateway is in scope, which must be settled before the first deployment (section 13.3).
7. Microsoft and Contoso deploy the Azure Migrate appliance at a pilot datacentre and manufacturing site.
8. Microsoft facilitate a discovery workshop, run in the two tracks described in section 11.
9. Contoso provide the production shutdown calendar and hardware lead times so the wave plan in section 8 can be dated.
10. Contoso produce the per-tier recovery objective table described in section 16.4.
11. Microsoft produce a detailed architecture and design rationale following discovery and Azure Migrate output.
