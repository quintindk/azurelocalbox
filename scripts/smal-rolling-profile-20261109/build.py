"""Derive a distinct one-effect worker/dispatcher proposal from canonical R2 mechanics.

No canonical write, transport, process dispatch or inherited approval. Credential/session
helper source is referenced from canonical bytes, not independently reconstructed.
"""
import base64
import argparse
import hashlib
import json
from pathlib import Path
import re
import plan

HERE=Path(__file__).resolve().parent
CANONICAL=HERE.parent.parent
# Compatibility placement only. Refuse silent re-derivation from changed R2 WIP.
INPUT_PINS={
    'common':'cd6c23414a3e791c992d3b552de57b254536e03e00ed2479865ea334bf4dbdbd',
    'worker':'5774d14e69b6b6122a1a0efe2b11e9e490b83672fa97283309fbff3568a0998e',
    'stage':'1a7ad99cdc44a867828a7b092b7a33a5a6baca865ef0dc26ad64ac3f3acc90c2',
    'startup':'a722ea416df9566fefbd62c092ffed6859ddf295204a3bd1353348574407f322',
}
BASE_RENDER_PINS={
    'common-render-fragment.ps1':'0e58f64f888c897a48b1d4f28bd6faec22346e9d8f1c36e4c92da29f0a2b6b86',
    'profile-worker-template.ps1':'9af1504e6623f4d107c7bd7753f64c4f2061ac3cb867df59cd5170ea445f5540',
    'profile-stage-template.ps1':'e603ff23bc453b727e0af9a5f44a161c2e734daee419d43ed1b47706b35eae1d',
    'proposed-canonical-startup.ps1':'657955dffbc22456863fe6360cc567adacc92e26d857904b20c26fbc5057face',
}
RENDER_PINS={**BASE_RENDER_PINS,'profile-worker-template.ps1':'34de22cab5991121641f6f6a919f3b9ae35305c866944a9b46ca97ad631138a3','profile-stage-template.ps1':'ef7c95089d2698575105bf7ec8abf6b8f29591d0036249d6f00755cfcdc05858'}
MOC_HELPER_SHA256='040b3c1e55ef5934eb76215d8c00b22730cc23136c5f61d6e50856eef81455c9'
OLD_ROOT=r'C:\ProgramData\AzureLocalBox\ComputeCapacity-R2-20261108-01'
NEW_ROOT=r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261109-01'


def render():
    paths={k:CANONICAL/'scripts'/v for k,v in {'common':'smal-compute-capacity-20261108-common.ps1','worker':'smal-compute-capacity-20261108-worker.ps1','stage':'smal-compute-capacity-20261108-stage.ps1','startup':'start-smal-existing-guests.ps1'}.items()}
    pins={str(p.relative_to(CANONICAL)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()}
    for key,path in paths.items():
        allowed={INPUT_PINS[key]}
        if key=='startup':allowed.add(BASE_RENDER_PINS['proposed-canonical-startup.ps1'])
        if pins[str(path.relative_to(CANONICAL))] not in allowed:
            raise ValueError('Canonical input differs from reviewed source: '+str(path.relative_to(CANONICAL)))
    common=paths['common'].read_text().replace(OLD_ROOT,NEW_ROOT)
    common=common.replace('maximumNumaMemory = $memory.MaximumAmountPerNumaNode','maximumNumaMemory = $memory.MaximumPerNumaNode')
    # Destructive progress requires current maintenance. Down-node reads and
    # start/resume compensation retain their original, separately scoped rules.
    maintenance="""    if (-not $compensating -and $current[0].state -cne 'Down') {
        Assert-Compute ($current[0].state -ceq 'Paused') 'Current selected node is not paused for stop'
        $selected = @($h.devices | Where-Object owner -CEQ $node)
        Assert-Compute ($selected.Count -eq 8 -and @($selected | Where-Object maintenance -NE $true).Count -eq 0) 'Current selected eight devices are not in maintenance'
        Assert-ComputeEqual @($selected.id | Sort-Object) @($expected | Sort-Object) 'Current maintenance device set differs'
    }
"""
    common=common.replace("    Assert-Compute ($h.allCsvOnline -and $h.quorumType",maintenance+"    Assert-Compute ($h.allCsvOnline -and $h.quorumType",1)
    common+="""
function Assert-ProfileInfrastructurePlacement($snapshot) {
    $capacities = if ($snapshot.nodeCapacity -is [Collections.IDictionary]) { @($snapshot.nodeCapacity.Values) } else { @($snapshot.nodeCapacity.PSObject.Properties | ForEach-Object Value) }
    $placements = @($capacities | ForEach-Object { $_.bridgePlacement } | Where-Object id -IEQ '4c6ca5cc-8c9a-499b-8ffe-c029bbfd3522')
    Assert-Compute ($placements.Count -eq 1 -and $placements[0].state -ceq 'Running' -and $placements[0].hciNode -cin @('LB-NODE02','LB-NODE03')) 'Infrastructure is not Running once on an expanded survivor'
    $owner = $placements[0].hciNode
    $guest = @($snapshot.guestsStatic | Where-Object name -CEQ $owner)
    Assert-Compute ($guest.Count -eq 1 -and $guest[0].cpu -eq 20 -and $guest[0].memory -eq 96GB -and $snapshot.states.$owner -ceq 'Running') 'Infrastructure survivor is not the admitted expanded Running guest'
}
"""
    worker=paths['worker'].read_text().replace(OLD_ROOT,NEW_ROOT).replace('transitionContract.version -ne 2','transitionContract.version -ne 3')
    worker="if ($null -eq $plan -or $plan.executionApproval.parentGo -ne $true -or [string]::IsNullOrEmpty($stage)) { throw 'Unsealed profile template is not executable' }\n"+worker
    begin=worker.index("            'cluster-stop' {");finish=worker.index("            'guest-stop' {",begin)
    worker=worker[:begin]+worker[finish:]
    guard="""    if ($entry.effect -cnotin @('drain','guest-stop','cpu','memory','guest-start','resume','infrastructure-return','complete')) { throw 'Effect outside exact rolling profile scope' }
    if ($plan.operationId -cne 'smal-foundation-profile-20261109-01' -or $plan.executionApproval.originalOperationsReconciled -ne $true) { throw 'New operation/original outcome reconciliation missing' }
    if ([DateTimeOffset]::UtcNow -ge [DateTimeOffset]::Parse($plan.executionApproval.expiresAt)) { throw 'Execution GO expired' }
    $target=@{'LB-NODE01'=@{cpu=16;memory=64GB};'LB-NODE02'=@{cpu=20;memory=96GB};'LB-NODE03'=@{cpu=20;memory=96GB}}
    if ($entry.effect -cin @('cpu','memory','guest-start') -and ($entry.targetCpu -ne $target[$entry.node].cpu -or $entry.targetMemoryBytes -ne $target[$entry.node].memory)) { throw 'Exact mixed-profile target differs' }
    if ($entry.effect -ceq 'memory' -and $entry.node -ceq 'LB-NODE01') { throw 'NODE01 has no memory change' }
"""
    worker=worker.replace("    $clusterRead =",guard+"    $clusterRead =",1)
    worker=worker.replace("    $state.rpcInvoked = $true;", "    if ([DateTimeOffset]::UtcNow -ge [DateTimeOffset]::Parse($plan.executionApproval.expiresAt)) { throw 'GO expired before RPC' }\n    $state.rpcInvoked = $true;",1)
    worker=worker.replace("$entry.effect -ceq 'resume'","$entry.effect -cin @('resume','guest-start')")
    stop_guard="""                $stopBefore = Read-ComputeSnapshot
                Assert-ComputeMaintenanceHealth $stopBefore $entry.node $proof $false
                $current = @($stopBefore.clusterHealth.nodeStates | Where-Object name -CEQ $entry.node)
                Assert-Compute ($current.Count -eq 1 -and $current[0].state -ceq 'Paused') 'Graceful stop requires current paused node'
                $devices = @($stopBefore.clusterHealth.devices | Where-Object owner -CEQ $entry.node)
                Assert-Compute ($devices.Count -eq 8 -and @($devices | Where-Object { $_.maintenance -ne $true -or @($_.operational | Where-Object { $_ -cin @('In Maintenance Mode','InMaintenanceMode') }).Count -eq 0 }).Count -eq 0) 'Graceful stop requires current eight-device maintenance'
                if ($entry.node -ceq 'LB-NODE01') { Assert-ProfileInfrastructurePlacement $stopBefore }
"""
    worker=worker.replace("            'guest-stop' {\n", "            'guest-stop' {\n"+stop_guard,1)
    worker=worker.replace("                Stop-VM -VM $vm -Confirm:$false -ErrorAction Stop", "                if ([DateTimeOffset]::UtcNow -ge [DateTimeOffset]::Parse($plan.executionApproval.expiresAt)) { throw 'GO expired before graceful stop' }\n                Stop-VM -VM $vm -Confirm:$false -ErrorAction Stop",1)
    worker=worker.replace("@('cluster-stop', 'drain', 'resume')","@('drain', 'resume','infrastructure-return')")
    worker=worker.replace('Set-VMMemory -VM $vm -StartupBytes 128GB -ErrorAction Stop',"$m=Get-VMMemory -VM $vm\n                if ($m.DynamicMemoryEnabled -or $m.Minimum -gt $entry.targetMemoryBytes -or $m.Maximum -lt $entry.targetMemoryBytes) { throw 'Native memory bounds differ' }\n                Set-VMMemory -VM $vm -StartupBytes $entry.targetMemoryBytes -ErrorAction Stop")
    worker=worker.replace('Set-VMProcessor -VM $vm -Count 16 -ErrorAction Stop',"$p=Get-VMProcessor -VM $vm\n                if (-not $p.ExposeVirtualizationExtensions -or $p.MaximumCountPerNumaNode -lt $entry.targetCpu -or $vm.Generation -ne 2 -or $vm.Version.ToString() -cne '12.0') { throw 'Native processor/version bounds differ' }\n                Set-VMProcessor -VM $vm -Count $entry.targetCpu -ErrorAction Stop")
    start="""            'guest-start' {
                $vm=Get-VM -Id $plan.guestIds.PSObject.Properties[$entry.node].Value
                if ($vm.Name -cne $entry.node -or $vm.State.ToString() -cne 'Off') { throw 'Exact independently admitted Off guest required' }
                if ($before.hostCapacity.freeMemoryBytes -lt ($entry.targetMemoryBytes+32GB)) { throw 'Physical start availability/outer reserve violated' }
                Start-VM -VM $vm -ErrorAction Stop
            }
            'infrastructure-return' {
                Invoke-Command -Session $session -ErrorAction Stop -ScriptBlock {
                    Move-ClusterVirtualMachineRole -Cluster smal-localbox01 -VMId '4c6ca5cc-8c9a-499b-8ffe-c029bbfd3522' -Node LB-NODE01 -MigrationType Live -ErrorAction Stop | Out-Null
                }
            }
            'complete' {
                $placements=@($before.nodeCapacity.Values | ForEach-Object {$_.bridgePlacement} | Where-Object id -IEQ '4c6ca5cc-8c9a-499b-8ffe-c029bbfd3522')
                if ($placements.Count -ne 1 -or $placements[0].state -cne 'Running' -or $placements[0].hciNode -cne 'LB-NODE01') { throw 'Final infrastructure owner differs' }
                $proof=@{planSha256=$planSha;sourceCommit=$sourceCommit;allHealthyAndOk=$true;noActiveStorageJobs=$true;finalProfiles=$entry.beforeProfiles;allOriginalOperationsReconciled=$true}
                [IO.File]::WriteAllText((Join-Path $root 'completion.json'),($proof|ConvertTo-Json -Depth 20 -Compress))
                $operation=Get-Content (Join-Path $root 'operation.json') -Raw|ConvertFrom-Json
                $operation.active=$false
                [IO.File]::WriteAllText((Join-Path $root 'operation.json'),($operation|ConvertTo-Json -Depth 20 -Compress))
            }
"""
    worker=worker.replace("            'startup-grant' {",start+"            'startup-grant' {",1)
    begin=worker.index("            'startup-grant' {");finish=worker.index("            default {",begin)
    worker=worker[:begin]+worker[finish:]
    worker=worker.replace("$vm.Version.ToString() -cne '12.0')", "$vm.Version.ToString() -cne '12.0' -or -not (Get-VMHost).NumaSpanningEnabled)")
    worker=worker.replace("                $proof=@{planSha256", "                foreach($guest in $before.guestsStatic) {\n                    $wanted=if($guest.name -ceq 'LB-DC01'){@{cpu=2;memory=4GB}}else{$target[$guest.name]}\n                    if ($guest.cpu -ne $wanted.cpu -or $guest.memory -ne $wanted.memory -or $before.states[$guest.name] -cne 'Running') { throw 'Final mixed profile/state differs' }\n                }\n                $proof=@{planSha256",1)
    worker=worker.replace("                $proof = @{ selectedNode", "                if ($entry.node -ceq 'LB-NODE01') {\n                    $placements=@($afterDrain.nodeCapacity.Values | ForEach-Object {$_.bridgePlacement} | Where-Object id -IEQ '4c6ca5cc-8c9a-499b-8ffe-c029bbfd3522')\n                    if ($placements.Count -ne 1 -or $placements[0].state -cne 'Running' -or $placements[0].hciNode -ceq 'LB-NODE01') { throw 'Infrastructure migration not independently established' }\n                }\n                $proof = @{ selectedNode",1)
    stage=paths['stage'].read_text().replace(OLD_ROOT,NEW_ROOT).replace('transitionContract.version -ne 2','transitionContract.version -ne 3')
    stage="if ($null -eq $plan -or $plan.executionApproval.parentGo -ne $true -or [string]::IsNullOrEmpty($stage)) { throw 'Unsealed profile dispatcher is not executable' }\n"+stage
    begin=stage.index("            $helperBytes =");finish=stage.index("            Write-R2NewJson",begin)
    stage=stage[:begin]+stage[finish:]
    stage=stage.replace('; startupHelperSha256 = $startupHelperSha256','')
    stage=stage.replace("                if ((Process-R2Alive $old) -ne $false -or $old.phase -cne 'returned')", "                if ($old.rpcInvoked -eq $true -and $old.outcome -ceq 'unknown') { throw 'Original RPC outcome unresolved; returned/dead is not independent settlement' }\n                if ((Process-R2Alive $old) -ne $false -or $old.phase -cne 'returned')",1)
    stage=stage.replace("phase = 'launch-pending'; pid = $PID;", "independentProofSha256 = $independentProofSha256; phase = 'launch-pending'; pid = $PID;",1)
    legacy=r"""    foreach($oldRoot in @('C:\ProgramData\AzureLocalBox\ComputeCapacity-20261108-01','C:\ProgramData\AzureLocalBox\ComputeCapacity-R2-20261108-01')) {
        if (Test-Path -LiteralPath $oldRoot) { throw 'Retained original operation requires separate exact reconciliation; no new-root bypass' }
    }
    if ([DateTimeOffset]::UtcNow -ge [DateTimeOffset]::Parse($plan.executionApproval.expiresAt)) { throw 'Dispatch GO expired' }
"""
    stage=stage.replace("    $mutex =",legacy+"    $mutex =",1)
    startup=paths['startup'].read_text()
    gate=r"""    $profileRoot='C:\ProgramData\AzureLocalBox\FoundationProfile-20261109-01'
    if (Test-Path -LiteralPath $profileRoot) {
        $operation=Get-Content (Join-Path $profileRoot 'operation.json') -Raw|ConvertFrom-Json
        $closed=Get-Content (Join-Path $profileRoot 'completion.json') -Raw|ConvertFrom-Json
        if ($operation.operationId -cne 'smal-foundation-profile-20261109-01' -or $operation.active -ne $false -or $closed.planSha256 -cne $operation.planSha256 -or $closed.sourceCommit -cne $operation.sourceCommit -or $closed.allHealthyAndOk -ne $true -or $closed.noActiveStorageJobs -ne $true -or $closed.allOriginalOperationsReconciled -ne $true) { throw 'Rolling profile operation is not closed; no normal startup' }
        foreach($file in @(Get-ChildItem $profileRoot -Filter 'worker-*.state.json' -File)) {
            $s=Get-Content $file.FullName -Raw|ConvertFrom-Json;$p=Get-Process -Id $s.pid -ErrorAction SilentlyContinue
            if ($s.phase -cne 'returned' -or ($p -and $p.StartTime.ToUniversalTime().ToString('o') -ceq $s.processStartedUtc)) { throw 'Original rolling worker unresolved; no normal startup' }
        }
        foreach($vm in @(Get-VM)) { $p=$closed.finalProfiles.PSObject.Properties[$vm.Name].Value;if ($null -eq $p -or $p.cpu -ne $vm.ProcessorCount -or $p.memory -ne $vm.MemoryStartup) { throw 'Completed rolling profiles drifted' } }
    }
"""
    # Installing the exact reviewed startup gate must not insert it twice or change
    # original worker/observe identity. No other startup revision is accepted above.
    if hashlib.sha256(paths['startup'].read_bytes()).hexdigest()==INPUT_PINS['startup']:
        startup=startup.replace('    $targets = @(',gate+'    $targets = @(',1)
    # No transport/secret-helper copy: common is still rendered from the canonical pinned library.
    files={'common-render-fragment.ps1':common,'profile-worker-template.ps1':worker,'profile-stage-template.ps1':stage,'proposed-canonical-startup.ps1':startup}
    # Verify the exact former v2 outputs before this separately-reviewed delta.
    for name,text in files.items():
        if hashlib.sha256(text.encode()).hexdigest()!=BASE_RENDER_PINS[name]:
            raise ValueError('Rendered source differs from accepted v2: '+name)
    helper_path=CANONICAL/'scripts/smal-rolling-profile-20261109/moc-contract.ps1'
    helper=helper_path.read_bytes()
    if hashlib.sha256(helper).hexdigest()!=MOC_HELPER_SHA256:raise ValueError('Canonical input differs: MOC helper source')
    pins[str(helper_path.relative_to(CANONICAL))]=MOC_HELPER_SHA256
    worker=worker.replace('transitionContract.version -ne 3','transitionContract.version -ne 4')
    worker=worker.replace("'drain','guest-stop'","'drain','moc-remove','moc-add','guest-stop'",1)
    worker=worker.replace("    $target=@", "    if ($plan.maximumExecutionDeadline -cne '2026-11-10T15:00:00+02:00' -or [DateTimeOffset]::Parse($plan.executionApproval.expiresAt) -gt [DateTimeOffset]::Parse($plan.maximumExecutionDeadline)) { throw 'GO exceeds fixed proposed phase bound' }\n    $target=@",1)
    worker=worker.replace("$entry.healthProfile -ceq 'selected-maintenance'","$entry.healthProfile -cin @('selected-maintenance','selected-return')",1)
    worker=worker.replace("$entry.effect -cin @('resume','guest-start')","$entry.effect -cin @('resume','guest-start','moc-add')",1)
    worker=worker.replace("@('drain', 'resume','infrastructure-return')","@('drain', 'resume','infrastructure-return','moc-remove','moc-add')",1)
    membership_preflight="""    $mocObserver = if ($entry.node -and $before.states[$entry.node] -ceq 'Running') { $entry.node } else { @($before.states.Keys | Where-Object { $_ -cne 'LB-DC01' -and $before.states[$_] -ceq 'Running' } | Sort-Object)[0] }
    $mocBefore = Read-ProfileMoc $mocObserver
    Assert-ProfileMocMembership $mocBefore $entry.beforeMocMembers $plan.mocContract
    if ($entry.effect -ceq 'moc-add') {
        $selected = @($before.clusterHealth.nodeStates | Where-Object name -CEQ $entry.node)
        Assert-Compute ($selected.Count -eq 1 -and $selected[0].state -ceq 'Up') 'MOC re-inclusion requires current Up node'
    }
"""
    worker=worker.replace('    if ((Get-VMHost).LogicalProcessorCount',membership_preflight+'    if ((Get-VMHost).LogicalProcessorCount',1)
    # Preserve the returned mutation RPC BEFORE a later read can fail. The event is
    # not settlement and never authorises repeating that original effect.
    returned="                $state.rpcReturned = $true; $state.outcome = 'rpc-returned-await-independent-observation'; Save-R2Worker 'rpc-returned'\n"
    worker=worker.replace("                $afterDrain = Read-ComputeSnapshot",returned+"                $state.postReadSucceeded = $false\n                $afterDrain = Read-ComputeSnapshot",1)
    worker=worker.replace("                $state.drainProof = $proof","                $state.drainProof = $proof\n                $state.postReadSucceeded = $true",1)
    moc_effect="""            { $_ -cin @('moc-remove','moc-add') } {
                $expectedBinding = $plan.mocContract.nodes.PSObject.Properties[$entry.node].Value
                $rpc = Invoke-Command -Session $session -ArgumentList $entry.node, $entry.effect, $expectedBinding, @($entry.beforeMocMembers), $ProfileMocRead.ToString() -ErrorAction Stop -ScriptBlock {
                    param($node, $effect, $binding, $beforeMembers, $readSource)
                    $ErrorActionPreference = 'Stop'
                    $read = & ([ScriptBlock]::Create($readSource)) $node
                    if ((@($read.members | Sort-Object) -join '|') -cne (@($beforeMembers | Sort-Object) -join '|')) { throw 'Actual MOC membership changed before mutation' }
                    foreach ($name in @('Get-MocPhysicalNode','Remove-MocPhysicalNode','New-MocPhysicalNode')) {
                        if ($read.commands[$name].contractSha256 -cne $binding.commands.PSObject.Properties[$name].Value.contractSha256) { throw 'Installed MOC binding changed before mutation' }
                    }
                    $name = if ($effect -ceq 'moc-remove') { 'Remove-MocPhysicalNode' } elseif ($effect -ceq 'moc-add') { 'New-MocPhysicalNode' } else { throw 'Unknown exact MOC effect' }
                    $command = @(Get-Command -Name $name -All -ErrorAction Stop)
                    if ($command.Count -ne 1 -or $command[0].ModuleName -cne $binding.commands.PSObject.Properties[$name].Value.moduleName) { throw 'MOC mutation binding is not unique/pinned' }
                    & $command[0] -NodeName $node | Out-Null
                    @{ rpcReturned = $true; node = $node; effect = $effect }
                }
                Assert-Compute ($rpc.rpcReturned -eq $true -and $rpc.node -ceq $entry.node -and $rpc.effect -ceq $entry.effect) 'Exact MOC mutation return missing'
                $state.rpcReturned = $true; $state.outcome = 'rpc-returned-await-independent-observation'; Save-R2Worker 'rpc-returned'
                $state.postReadSucceeded = $false
                $mocAfter = Read-ProfileMoc $entry.node
                Assert-ProfileMocMembership $mocAfter $entry.afterMocMembers $plan.mocContract
                $state.mocMembership = @($mocAfter.members); $state.postReadSucceeded = $true
            }
"""
    worker=worker.replace("            'guest-start' {",moc_effect+"            'guest-start' {",1)
    # A fresh MOC exclusion must still hold immediately at graceful stop, not only
    # in an old phase proof. Existing current Paused/eight-device/placement guards stay.
    worker=worker.replace('                $stopBefore = Read-ComputeSnapshot',"                $stopMoc = Read-ProfileMoc $entry.node\n                Assert-ProfileMocMembership $stopMoc $entry.beforeMocMembers $plan.mocContract\n                $stopBefore = Read-ComputeSnapshot",1)
    worker=worker.replace("        $state.outcome = 'rpc-returned-await-independent-observation'","        $state.rpcReturned = $true\n        $state.outcome = 'rpc-returned-await-independent-observation'",1)
    worker=worker.replace("    $state.errorType =", "    if ($state.rpcReturned -eq $true -and $state.postReadSucceeded -eq $false) { $state.outcome = 'rpc-returned-postread-failed-await-independent-observation' }\n    $state.errorType =",1)
    worker=helper.decode()+'\n'+worker
    stage=stage.replace('transitionContract.version -ne 3','transitionContract.version -ne 4')
    observe="""    $mocObservation = $null
    try {
        $observer = @($profiles | Where-Object { $_.name -cne 'LB-DC01' -and $_.state -ceq 'Running' } | Sort-Object name)[0].name
        if ($observer) { $mocObservation = Read-ProfileMoc $observer }
    } catch { $mocObservation = @{ status = 'failed-read-only'; errorType = $_.Exception.GetType().Name } }
"""
    stage=stage.replace("    @{ status = 'complete'; atUtc",observe+"    @{ status = 'complete'; atUtc",1)
    stage=stage.replace('rpcPhase = $(if ($worker)', 'mocObservation = $mocObservation; effectSettled = $false; rpcPhase = $(if ($worker)',1)
    stage=helper.decode()+'\n'+stage
    files['profile-worker-template.ps1']=worker;files['profile-stage-template.ps1']=stage
    for name,text in files.items():
        if hashlib.sha256(text.encode()).hexdigest()!=RENDER_PINS[name]:raise ValueError('Rendered source differs from proposed MOC delta: '+name)
    return files,pins


def qualifier():
    files,_=render()
    common=files['common-render-fragment.ps1']
    # Exact function slices, not a second snapshot reader or reconstructed credential
    # flow. Metadata qualification needs only the existing assertion/session helpers.
    session_helpers=common[common.index('function Assert-Compute('):common.index('function Get-ComputeKeys')]+common[common.index('function New-ComputeSession'):common.index('function Read-ComputeSnapshot')]
    context=base64.b64encode(json.dumps({'guestIds':plan.IDS,'transitionContract':{'deviceOwners':{}}},separators=(',',':')).encode()).decode()
    prefix="$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n$entry=$null\nif($env:COMPUTERNAME -cne 'LocalBox-Client'){throw 'Wrong outer host'}\n$deadline=[DateTimeOffset]::Parse('2026-11-10T15:00:00+02:00')\nif([DateTimeOffset]::UtcNow -ge $deadline){throw 'Fixed MOC qualifier window closed'}\n$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+context+"'))|ConvertFrom-Json)\n"
    helper=(CANONICAL/'scripts/smal-rolling-profile-20261109/moc-contract.ps1').read_text()
    suffix="""
$nodes=[ordered]@{}
foreach($node in @('LB-NODE02','LB-NODE03','LB-NODE01')) {
    if([DateTimeOffset]::UtcNow -ge $deadline){throw 'Fixed MOC qualifier window closed'}
    $nodes[$node]=Read-ProfileMoc $node $true
}
if([DateTimeOffset]::UtcNow -ge $deadline){throw 'Fixed MOC qualifier window closed after reads'}
@{status='complete';mutationPerformed=$false;atUtc=[datetime]::UtcNow.ToString('o');commonSourceSha256='0e58f64f888c897a48b1d4f28bd6faec22346e9d8f1c36e4c92da29f0a2b6b86';nodes=$nodes}|ConvertTo-Json -Depth 30 -Compress
"""
    return prefix+session_helpers+'\n'+helper+'\n'+suffix


def capsule(value,stage,source_commit='UNPUBLISHED',mode='dispatch'):
    # Assembly only. Human review/publication and a fresh sealed plan are separate gates.
    if stage not in plan.stages() or mode not in ('dispatch','observe'):raise ValueError('Exact phase stage/mode required')
    if source_commit!='UNPUBLISHED' and not re.fullmatch(r'[0-9a-f]{40}',source_commit):raise ValueError('Exact source checkpoint hash required')
    if value['operationId']!='smal-foundation-profile-20261109-01' or value['guestIds']!=plan.IDS:raise ValueError('Exact operation/VM IDs required')
    if value['executionApproval']['parentGo'] is True:
        if source_commit=='UNPUBLISHED':raise ValueError('No unpublished effect capsule')
        # Original-operation observation remains possible after expiry/unknown profile outcome.
        # Its GET-only stage verifies original request/plan/worker hashes; it cannot dispatch.
        if mode=='dispatch':plan.execution_preflight(value,stage,value['independentProof'])
    expected=plan.stages()[stage]
    if value['transitionContract']['stages'][stage]!=expected:raise ValueError('Immutable stage/target delta differs')
    # Fresh stage evidence is not part of the immutable operation or worker bytes.
    # Keep worker/source/request identity reproducible for original observe calls.
    immutable={key:item for key,item in value.items() if key!='independentProof'}
    files,pins=render();raw=json.dumps(immutable,sort_keys=True,separators=(',',':')).encode();digest=hashlib.sha256(raw).hexdigest()
    prefix="$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(raw).decode()+"'))|ConvertFrom-Json)\n"
    prefix+="$stage='"+stage+"'\n$effectKey='"+expected['key']+"'\n$planSha='"+digest+"'\n$sourceCommit='"+source_commit+"'\n"
    worker=prefix+files['common-render-fragment.ps1']+'\n'+files['profile-worker-template.ps1']
    worker_sha=hashlib.sha256(worker.encode()).hexdigest().upper()
    evidence={'operationPlanSha256':digest,'sourceCommit':source_commit,'stage':stage,'proof':value.get('independentProof')}
    evidence_raw=json.dumps(evidence,sort_keys=True,separators=(',',':')).encode()
    evidence_sha=hashlib.sha256(evidence_raw).hexdigest()
    dispatch=prefix+"$mode='"+mode+"'\n$independentProofSha256='"+evidence_sha+"'\n$workerSha256='"+worker_sha+"'\n$workerBase64='"+base64.b64encode(worker.encode()).decode()+"'\n"
    dispatch+=files['common-render-fragment.ps1']+'\n'+files['profile-stage-template.ps1']
    return {'worker':worker,'dispatcher':dispatch,'planSha256':digest,'sourcePins':pins,'independentProof':evidence,'independentProofSha256':evidence_sha}


if __name__=='__main__':
    # Offline JSON only, matching the canonical capacity renderer convention.
    # Publication, existing transport and native GO remain the parent's responsibility.
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('render','capsule','qualifier'))
    parser.add_argument('--plan',type=Path)
    parser.add_argument('--stage',choices=tuple(plan.stages()))
    parser.add_argument('--source-commit',default='UNPUBLISHED')
    parser.add_argument('--mode',choices=('dispatch','observe'),default='dispatch')
    args=parser.parse_args()
    if args.action=='qualifier':
        result={'files':{'scripts/read-smal-rolling-moc-contract.ps1':qualifier()},'executionApproved':False}
    elif args.action=='render':
        files,pins=render()
        result={'files':files,'sourcePins':pins,'unsealedPlan':plan.candidate(),'executionApproved':False}
    else:
        if args.plan is None or args.stage is None:parser.error('capsule requires --plan and --stage')
        result=capsule(json.loads(args.plan.read_text()),args.stage,args.source_commit,args.mode)
    print(json.dumps(result,indent=2))
