"""Private remaining-phase assembly. Unknown handoff/qv2 facts fail closed; no execution."""
import base64
import hashlib
import json
from pathlib import Path
import re
import plan

HERE=Path(__file__).resolve().parent
CANONICAL=plan.CANONICAL
BASE_WORKER='scripts/rolling-profile-live-20261110-02/drain-LB-NODE02.worker.ps1'
BASE_WORKER_SHA='fd02e48b96d93b2631687808e92642d6a4d5ec44a0e2f2e8fc6e685ef95f4998'
BASE_DISPATCH='scripts/rolling-profile-live-20261110-02/drain-LB-NODE02.dispatch.ps1'
BASE_DISPATCH_SHA='9fcf69dd047b14739c961b8ce5275ece9522f831db4b6f491e8ada72331ed94d'
JOURNAL_SHA='b6ba06aa3f687077d2a1d22f045a3ad5eb58aca5f7f45f981836a84db162b807'
OLD_WRITER="    if (Test-Path $statePath) { [IO.File]::Replace($tmp, $statePath, $null) } else { [IO.File]::Move($tmp, $statePath) }"
NEW_WRITER="    if (Test-Path $statePath) { $backup = $statePath + '.before-sequence-' + $state.sequence + '.' + $state.invocationAttempt + '.json'; if (Test-Path -LiteralPath $backup) { throw 'Journal backup already exists; no overwrite' }; [IO.File]::Replace($tmp, $statePath, $backup) } else { [IO.File]::Move($tmp, $statePath) }"
sha=lambda b:hashlib.sha256(b).hexdigest()


def read(name,pin):
    raw=(CANONICAL/name).read_bytes()
    if sha(raw)!=pin:raise ValueError('Pinned original source differs: '+name)
    return raw.decode()


def replace_once(text,before,after):
    if text.count(before)!=1:raise ValueError('Reviewed source boundary differs: '+before[:80])
    return text.replace(before,after,1)


def handoff_helpers():
    source=(HERE/'handoff.ps1.in').read_text()
    return source.replace('@@ALL_KEYS_JSON@@',json.dumps(plan.ALL_KEYS)).replace('@@ROWS_BASE64@@',base64.b64encode(json.dumps(plan._whole_stages(),separators=(',',':')).encode()).decode())


def source_binding(required=False):
    binding=json.loads((HERE/'qualification-binding.json').read_text())
    complete=binding.get('finalQv2FactorySha256')==plan.QV2_FACTORY_SHA and all(plan.pin(binding.get(k)) for k in ('qualified03JobsSourceSha256','supervisionTemplateSha256'))
    if required and not complete:raise ValueError('Final accepted qv2/03-scope/supervision pins remain unbound')
    return binding,complete


def policy_source():
    binding,complete=source_binding()
    if not complete:return "function Assert-QualifiedMirrorJobs($h,[bool]$compensating=$false){throw 'Final qv2/03 scope source is unbound'}\n",binding
    path=HERE/binding['qualified03JobsSourceFile'];raw=path.read_bytes()
    if sha(raw)!=binding['qualified03JobsSourceSha256']:raise ValueError('Final qualified03 maintenance bytes differ')
    text=raw.decode()
    if 'Assert-QualifiedMirrorJobs' not in text or plan.OPERATION_ID not in text or plan.DEADLINE not in text:raise ValueError('Qualification owner must supply the exact03-scoped final predicate, not02 authority')
    return text,binding


def correct_moc_peer(helpers,worker,stage):
    peer_source=(HERE/'moc-peer.ps1.in').read_text()
    helpers=peer_source+'\n'+helpers
    helpers=replace_once(helpers,'    $mocSession = New-ComputeSession $node',"    $expectedPeer=Get-ProfileMocPeer $entry.node $null\n    Assert-Compute ($node -ceq $expectedPeer -and $node -cne $entry.node) 'MOC reader must execute on exact fixed peer, not target'\n    $mocSession = New-ComputeSession $node")
    old_observer="    $mocObserver = if ($entry.node -and $before.states[$entry.node] -ceq 'Running') { $entry.node } else { @($before.states.Keys | Where-Object { $_ -cne 'LB-DC01' -and $before.states[$_] -ceq 'Running' } | Sort-Object)[0] }"
    worker=replace_once(worker,old_observer,"    $mocObserver=Get-ProfileMocPeer $entry.node $before\n    $state.mocExecutingPeer=$mocObserver; $state.mocTarget=$entry.node")
    worker=replace_once(worker,'        $session = New-ComputeSession $target',"        $sessionNode=if($entry.effect -cin @('moc-remove','moc-add')){$mocObserver}else{$target}\n        if($entry.effect -cin @('moc-remove','moc-add')){Assert-Compute ($sessionNode -cne $entry.node -and $sessionNode -ceq (Get-ProfileMocPeer $entry.node $before)) 'MOC caller must be exact healthy peer'}\n        $session = New-ComputeSession $sessionNode")
    worker=replace_once(worker,'$stopMoc = Read-ProfileMoc $entry.node','$stopMoc = Read-ProfileMoc $mocObserver')
    worker=replace_once(worker,'$expectedBinding = $plan.mocContract.nodes.PSObject.Properties[$entry.node].Value','$expectedBinding = $plan.mocContract.nodes.PSObject.Properties[$mocObserver].Value')
    worker=replace_once(worker,'-ArgumentList $entry.node, $entry.effect, $expectedBinding,','-ArgumentList $entry.node, $mocObserver, $entry.effect, $expectedBinding,')
    worker=replace_once(worker,'param($node, $effect, $binding, $beforeMembers, $readSource, $identityBinding)',"param($node, $peer, $effect, $binding, $beforeMembers, $readSource, $identityBinding)\n                    $exactPeers=@{'LB-NODE02'='LB-NODE01';'LB-NODE03'='LB-NODE01';'LB-NODE01'='LB-NODE02'}\n                    if($peer -cne $exactPeers[$node] -or $peer -ceq $node -or $env:COMPUTERNAME -cne $peer){throw 'MOC executing hostname/peer differs or equals target; no fallback'}")
    worker=replace_once(worker,'$read = & ([ScriptBlock]::Create($readSource)) $node $false $identityBinding','$read = & ([ScriptBlock]::Create($readSource)) $peer $false $identityBinding')
    worker=replace_once(worker,"if ($read.qualified -ne $true -or $read.membershipObserved -ne $true)","if ($read.observerNode -cne $peer -or $binding.observerNode -cne $peer -or $read.qualified -ne $true -or $read.membershipObserved -ne $true)")
    worker=replace_once(worker,'@{ rpcReturned = $true; node = $node; effect = $effect }','@{ rpcReturned = $true; node = $node; executingPeer = $peer; effect = $effect }')
    worker=replace_once(worker,'$rpc.rpcReturned -eq $true -and $rpc.node -ceq $entry.node -and $rpc.effect -ceq $entry.effect','$rpc.rpcReturned -eq $true -and $rpc.node -ceq $entry.node -and $rpc.executingPeer -ceq $mocObserver -and $rpc.effect -ceq $entry.effect')
    worker=replace_once(worker,'$mocAfter = Read-ProfileMoc $entry.node','$mocAfter = Read-ProfileMoc $mocObserver')
    old="        $observer = @($profiles | Where-Object { $_.name -cne 'LB-DC01' -and $_.state -ceq 'Running' } | Sort-Object name)[0].name"
    stage=replace_once(stage,old,"        if($null -eq $health){throw 'Existing observer health snapshot required for MOC peer qualification'}\n        $observer=Get-ProfileMocPeer $entry.node $health")
    return helpers,worker,stage


def render():
    read('scripts/smal-rolling-profile-20261110/journal_correction.py',JOURNAL_SHA)
    base=read(BASE_WORKER,BASE_WORKER_SHA)
    body=base[base.index('# Template only. Rendered stages'):]
    worker_start=body.index("if ($null -eq $plan -or $plan.executionApproval.parentGo")
    helpers=body[:worker_start];worker=body[worker_start:]
    helpers=helpers.replace(plan.ORIGIN_ROOT,plan.ROOT)
    # Accepted qv2 predicate is source-bound. Actual03 policy acceptance must still
    # be explicit in the create-only handoff, never inferred from this source copy.
    jobs,binding=policy_source()
    begin=helpers.index('    # No arbitrary job allowance.')
    end=helpers.index('\n}\n\nfunction Assert-ProfileInfrastructurePlacement',begin)
    helpers=helpers[:begin]+"    Assert-QualifiedMirrorJobs $h $compensating\n"+helpers[end:]
    helpers=helpers.replace('function Assert-ComputeMaintenanceHealth(',jobs+'\nfunction Assert-ComputeMaintenanceHealth(',1)
    helpers=helpers.replace("('"+plan.ROOT+"\\drain-proof-' + $selectedNode + '.json')", "((Get-RemainingDrainRoot $selectedNode) + '\\drain-proof-' + $selectedNode + '.json')")
    drain_root=r"""
function Get-RemainingDrainRoot([string]$node){
 if($node -ceq 'LB-NODE02'){
  $p=$plan.predecessorHandoff.record.retainedOriginalDrainProof
  if($p.file -cne 'drain-proof-LB-NODE02.json'){throw 'Exact original02 drain proof path differs'}
  $original=Read-RemainingControl ('C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-02\'+$p.file) $p.sha256
  if($original.planSha256 -cne $p.planSha256 -or $original.sourceCommit -cne $p.sourceCommit -or $original.selectedNode -cne $node -or $original.rpcReturned -ne $true -or $original.eightDevicesMaintenanceVerified -ne $true){throw 'Original02 drain proof identity/qualification differs'}
  return 'C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-02'
 }
 return 'C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-03'
}
"""
    helpers=handoff_helpers()+'\n'+drain_root+helpers
    worker=worker.replace(plan.ORIGIN_ROOT,plan.ROOT).replace(plan.ORIGIN_ID,plan.OPERATION_ID).replace('2026-11-10T20:00:00+02:00',plan.DEADLINE)
    worker=replace_once(worker,OLD_WRITER,NEW_WRITER)
    worker=worker.replace("(Join-Path $root ('drain-proof-' + $entry.node + '.json'))", "(Join-Path (Get-RemainingDrainRoot $entry.node) ('drain-proof-' + $entry.node + '.json'))")
    metadata="$state.businessBaseOperationId='"+plan.ORIGIN_ID+"'\n$state.businessBasePlanSha256='"+plan.ORIGIN_PLAN_SHA+"'\n$state.businessBaseSourceCommit='"+plan.ORIGIN_COMMIT+"'\n$state.businessBaseWorkerSha256='"+BASE_WORKER_SHA+"'\n$state.journalCorrectionFactorySha256='"+JOURNAL_SHA+"'\n$state.invocationAttempt='remaining03-'+$stage.ToLowerInvariant()+'-01'\n$state.predecessorHandoffSha256=$plan.predecessorHandoff.recordSha256\n"
    worker=worker.replace('function Save-R2Worker(',metadata+'function Save-R2Worker(',1)
    qualification_gate="    throw 'Accepted qv2/03 source is unbound'\n" if not source_binding()[1] else "    if($plan.maintenanceQualification.qualified03JobsSourceSha256 -cne '"+binding['qualified03JobsSourceSha256']+"' -or $plan.maintenanceQualification.parent03ScopeDecisionSha256 -cne $plan.predecessorHandoff.recordSha256){throw 'qv2/new03 scope differs'}\n"
    gate="    $h=Read-Remaining02Handoff $plan.predecessorHandoff.recordSha256\n    if(@($h.unexecutedSuffix) -cnotcontains $stage -or @($plan.transitionContract.stages.PSObject.Properties).Count -ne @($h.unexecutedSuffix).Count){throw 'Completed stage replay or wrong suffix'}\n"+qualification_gate
    worker=worker.replace("    Save-R2Worker 'preflight'",gate+"    Save-R2Worker 'preflight'",1)
    worker=replace_once(worker,'allOriginalOperationsReconciled=$true}',"allOriginalOperationsReconciled=$true;predecessorHandoffSha256=$plan.predecessorHandoff.recordSha256;predecessorPlanSha256='"+plan.ORIGIN_PLAN_SHA+"'}")
    source=read(BASE_DISPATCH,BASE_DISPATCH_SHA)
    stage=source[source.index('# R2 dispatch/observe template.'):]
    stage=stage.replace(plan.ORIGIN_ROOT,plan.ROOT).replace(plan.ORIGIN_ID,plan.OPERATION_ID).replace('2026-11-10T20:00:00+02:00',plan.DEADLINE)
    stage="if($null -eq $plan -or $plan.executionApproval.parentGo -ne $true){throw 'Unsealed remaining dispatcher'}\n"+stage
    stage=stage.replace("$workerFile = Join-Path $root ('worker-' + $stage + '.ps1')", "$workerFile = Join-Path $root ('worker-' + $stage + '.journal-fixed-01.ps1')")
    # Preserve all old01/legacy refusals; retained02 is inspected, never ignored.
    stage=replace_once(stage,'    $mutex =',"    $null=Read-Remaining02Handoff $plan.predecessorHandoff.recordSha256\n"+qualification_gate+"    if($plan.maximumExecutionDeadline -cne '"+plan.DEADLINE+"' -or [DateTimeOffset]::Parse($plan.executionApproval.expiresAt) -gt [DateTimeOffset]::Parse($plan.maximumExecutionDeadline)){throw 'Remaining phase bound differs'}\n    $mutex =")
    stage=replace_once(stage,'sourceCommit = $sourceCommit; active = $true }','sourceCommit = $sourceCommit; active = $true; predecessorHandoffSha256 = $plan.predecessorHandoff.recordSha256 }')
    helpers,worker,stage=correct_moc_peer(helpers,worker,stage)
    peer_sha=sha((HERE/'moc-peer.ps1.in').read_bytes())
    worker=replace_once(worker,'function Save-R2Worker(',"$state.mocPeerCorrectionSha256='"+peer_sha+"'\n$state.originalMocRefusalReconciliationSha256='"+plan.MOC_RECONCILIATION_SHA+"'\nfunction Save-R2Worker(")
    return {'common.ps1':helpers,'worker.ps1':worker,'stage.ps1':stage,'qualificationBinding':binding}


def capsule(value,stage,source_commit='UNPUBLISHED',mode='dispatch'):
    handoff=value.get('predecessorHandoff')
    if not isinstance(handoff,dict):raise ValueError('Actual accepted boundary required before suffix assembly')
    plan.validate_handoff(handoff['record']);rows=plan.stages(handoff['record'])
    if stage not in rows or mode not in ('dispatch','observe'):raise ValueError('Exact unexecuted suffix stage/mode required')
    if value.get('operationId')!=plan.OPERATION_ID or value.get('transitionContract',{}).get('stages')!=rows:raise ValueError('Exact new operation/suffix contract differs')
    if source_commit!='UNPUBLISHED' and not re.fullmatch('[a-f0-9]{40}',source_commit):raise ValueError('Exact source checkpoint required')
    if value['executionApproval']['parentGo'] is True:
        binding,_=source_binding(required=True)
        if source_commit=='UNPUBLISHED':raise ValueError('No unpublished effect capsule')
        if mode=='dispatch':plan.execution_preflight(value,stage,value['independentProof'])
        if any(value['maintenanceQualification'][k]!=binding[k] for k in ('finalQv2FactorySha256','qualified03JobsSourceSha256')) or value['maintenanceQualification']['parent03ScopeDecisionSha256']!=handoff['recordSha256']:raise ValueError('Plan/source/actual parent03 scope differs')
    files=render();immutable={k:v for k,v in value.items() if k!='independentProof'}
    raw=json.dumps(immutable,sort_keys=True,separators=(',',':')).encode();digest=sha(raw);entry=rows[stage]
    prefix="$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(raw).decode()+"'))|ConvertFrom-Json)\n$stage='"+stage+"'\n$effectKey='"+entry['key']+"'\n$planSha='"+digest+"'\n$sourceCommit='"+source_commit+"'\n"
    worker=prefix+files['common.ps1']+'\n'+files['worker.ps1'];worker_sha=sha(worker.encode())
    evidence={'operationPlanSha256':digest,'sourceCommit':source_commit,'stage':stage,'proof':value.get('independentProof')};evidence_sha=sha(json.dumps(evidence,sort_keys=True,separators=(',',':')).encode())
    dispatcher=prefix+"$mode='"+mode+"'\n$independentProofSha256='"+evidence_sha+"'\n$workerSha256='"+worker_sha.upper()+"'\n$workerBase64='"+base64.b64encode(worker.encode()).decode()+"'\n"+files['common.ps1']+'\n'+files['stage.ps1']
    result={'worker':worker,'dispatcher':dispatcher,'planSha256':digest,'workerSha256':worker_sha,'independentProof':evidence,'independentProofSha256':evidence_sha,'requiresAcceptedSynchronousSupervision':mode=='dispatch'}
    if mode=='dispatch' and value['executionApproval']['parentGo'] is True:
        binding,_=source_binding(required=True);raw=(HERE/binding['supervisionTemplateFile']).read_bytes()
        if sha(raw)!=binding['supervisionTemplateSha256']:raise ValueError('Accepted supervision source differs')
        template=raw.decode().replace(plan.ORIGIN_ROOT,plan.ROOT).replace('2026-11-10T20:00:00+02:00',plan.DEADLINE)
        correction={'businessBaseOperationId':plan.ORIGIN_ID,'businessBasePlanSha256':plan.ORIGIN_PLAN_SHA,
            'businessBaseSourceCommit':plan.ORIGIN_COMMIT,'businessBaseWorkerSha256':BASE_WORKER_SHA,
            'journalCorrectionFactorySha256':JOURNAL_SHA,'invocationAttempt':'remaining03-'+stage.lower()+'-01',
             'predecessorHandoffSha256':value['predecessorHandoff']['recordSha256'],
             'mocPeerCorrectionSha256':sha((HERE/'moc-peer.ps1.in').read_bytes()),'originalMocRefusalReconciliationSha256':plan.MOC_RECONCILIATION_SHA}
        supervision={'operationId':plan.OPERATION_ID,'planSha256':digest,'sourceCommit':source_commit,'stage':stage,
            'remoteWorkerName':'worker-'+stage+'.journal-fixed-01.ps1','workerSha256':worker_sha,
            'dispatcherSha256':sha(dispatcher.encode()),'independentProofSha256':evidence_sha,'correction':correction}
        if template.count('@@BINDING_JSON@@')!=1 or template.count('@@DISPATCH_BASE64@@')!=1:raise ValueError('Accepted fixed supervision interface differs')
        result['supervisedDispatcher']=template.replace('@@BINDING_JSON@@',json.dumps(supervision,sort_keys=True,separators=(',',':'))).replace('@@DISPATCH_BASE64@@',base64.b64encode(dispatcher.encode()).decode())
    return result


def install_handoff_source(record):
    plan.validate_handoff(record)
    raw=json.dumps(record,sort_keys=True,separators=(',',':')).encode();digest=sha(raw)
    return "$ErrorActionPreference='Stop'\nif($env:COMPUTERNAME -cne 'LocalBox-Client'){throw 'Wrong handoff host'}\n"+handoff_helpers()+"\n$bytes=[Convert]::FromBase64String('"+base64.b64encode(raw).decode()+"')\n$h=([Text.Encoding]::UTF8.GetString($bytes)|ConvertFrom-Json)\n$now=[DateTimeOffset]::UtcNow\n$at=[DateTimeOffset]::Parse($h.postconditions.observedAtUtc)\nif($now -ge [DateTimeOffset]::Parse('"+plan.DEADLINE+"') -or ($now-$at).TotalSeconds -lt 0 -or ($now-$at).TotalSeconds -gt 300){throw 'Actual handoff observation/window stale'}\nif(Test-Path '"+plan.ROOT+"'){throw '03 already has history; no handoff installation'}\n$mutex=[Threading.Mutex]::new($false,'Global\\AzureLocalBoxComputeCapacityR2');$held=$false\ntry{$held=$mutex.WaitOne(0);if(-not $held){throw 'Capacity work active'};Assert-Remaining02Evidence $h\nforeach($g in Get-VM){$wanted=$h.postconditions.profiles.PSObject.Properties[$g.Name].Value;if($null -eq $wanted -or $g.State.ToString() -cne $h.postconditions.states.PSObject.Properties[$g.Name].Value -or $g.ProcessorCount -ne $wanted.cpu -or $g.MemoryStartup -ne $wanted.memory){throw 'Actual handoff profile/state changed'}}\n$path='"+plan.ORIGIN_ROOT+'\\'+plan.HANDOFF_FILE+"'\n$f=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read);try{$f.Write($bytes,0,$bytes.Length);$f.Flush($true)}finally{$f.Dispose()}\n@{status='exact-prefix-handoff-recorded';recordSha256='"+digest+"';originalOperationRecordUnchanged=$true;newOperationGo=$false}|ConvertTo-Json -Compress\n}finally{if($held){$mutex.ReleaseMutex()};$mutex.Dispose()}\n",digest


def startup(original):
    if sha(original.encode())!='deaa978655dcbc90f488479c0c4bd0e523bfc3a697db464c47effcfc136130fe':raise ValueError('Startup preimage differs; preserve current source')
    begin=original.index("    $profileRoot='"+plan.ORIGIN_ROOT+"'")
    end=original.index('    $targets = @(',begin)
    old_gate=original[begin:end]
    new_gate=r"""
    $remainingRoot='C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-03'
    function Assert-RemainingStartup {
        $operation=Get-Content (Join-Path $remainingRoot 'operation.json') -Raw|ConvertFrom-Json
        $closed=Get-Content (Join-Path $remainingRoot 'completion.json') -Raw|ConvertFrom-Json
        if($operation.operationId -cne 'smal-foundation-profile-20261110-03' -or $operation.active -ne $false -or $closed.planSha256 -cne $operation.planSha256 -or $closed.sourceCommit -cne $operation.sourceCommit -or $closed.allHealthyAndOk -ne $true -or $closed.noActiveStorageJobs -ne $true -or $closed.allOriginalOperationsReconciled -ne $true -or $closed.predecessorHandoffSha256 -cne $operation.predecessorHandoffSha256 -or $closed.predecessorPlanSha256 -cne 'c6b4dfdfb3e1170129c8d578d3a87794d9ec41142275ed69c5decc2fb6006d53'){throw '03 active/incomplete or predecessor completion differs; no normal startup'}
        $null=Read-Remaining02Handoff $operation.predecessorHandoffSha256
        foreach($file in @(Get-ChildItem $remainingRoot -Filter 'worker-*.state.json' -File)){
            $s=Get-Content $file.FullName -Raw|ConvertFrom-Json;$p=Get-Process -Id $s.pid -ErrorAction SilentlyContinue
            if($s.phase -cne 'returned' -or ($s.rpcInvoked -eq $true -and $s.outcome -ceq 'unknown') -or ($p -and $p.StartTime.ToUniversalTime().ToString('o') -ceq $s.processStartedUtc)){throw '03 original process/RPC unresolved; no normal startup'}
        }
        $vms=@(Get-VM);if($vms.Count -ne 4){throw 'Exact four guests required'}
        foreach($vm in $vms){$wanted=$closed.finalProfiles.PSObject.Properties[$vm.Name].Value;$cpu=if($vm.Name -ceq 'LB-DC01'){2}elseif($vm.Name -ceq 'LB-NODE01'){16}else{20};$memory=if($vm.Name -ceq 'LB-DC01'){4GB}elseif($vm.Name -ceq 'LB-NODE01'){64GB}else{96GB};if($null -eq $wanted -or $wanted.cpu -ne $cpu -or $wanted.memory -ne $memory -or $vm.ProcessorCount -ne $cpu -or $vm.MemoryStartup -ne $memory){throw 'Completed03 current/final profiles differ'}}
    }
"""
    wrapped="    if((Test-Path '"+plan.ORIGIN_ROOT+"') -and (Test-Path '"+plan.ORIGIN_ROOT+'\\'+plan.HANDOFF_FILE+"')){\n        if(-not(Test-Path $remainingRoot)){throw '02 handed off but03 incomplete; no normal startup'}\n        Assert-RemainingStartup\n    }else{\n"+old_gate+"    }\n    if(Test-Path $remainingRoot){Assert-RemainingStartup}\n"
    # Prior01/legacy/R2 blocks remain byte-for-byte; the old02 gate remains the
    # unchanged else branch. Only an exact handoff AND completed03 can replace it.
    return original[:begin]+new_gate+handoff_helpers()+'\n'+wrapped+original[end:]


def baseline(handoff,moc_contract,admission):
    plan.validate_handoff(handoff['record'])
    if plan.digest(handoff['record'])!=handoff['recordSha256']:raise ValueError('Exact actual handoff bytes must be bound before baseline assembly')
    plan.moc_contract_preflight(moc_contract)
    base=read(BASE_WORKER,BASE_WORKER_SHA);match=re.search(r"^\$plan=.*?FromBase64String\('([^']+)'\)",base,re.M);origin=json.loads(base64.b64decode(match[1]))
    record=handoff['record'];first=next(iter(plan.stages(record).values()));selected=first['node'] if first['healthProfile']!='strict' else None
    if not isinstance(admission,dict) or not admission.get('volumeBudgets') or not all(isinstance(admission.get(k),int) and admission[k]>=0 for k in ('requiredPhysicalFreeBytes','repairReserveBytes')):raise ValueError('Actual closed volume/S2D reserve admission required')
    files=render();context={'operationId':plan.OPERATION_ID,'maximumExecutionDeadline':plan.DEADLINE,'guestIds':plan.IDS,'transitionContract':{'deviceOwners':record['postconditions']['deviceOwners']},'mocContract':moc_contract,'predecessorHandoff':handoff,'baseline':origin['baseline'],'admission':admission}
    raw=base64.b64encode(json.dumps(context,sort_keys=True,separators=(',',':')).encode()).decode()
    prefix="$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n$entry=[pscustomobject]@{node='"+first['node']+"'}\nif($env:COMPUTERNAME -cne 'LocalBox-Client'){throw 'Wrong remaining baseline host'}\n$end=[DateTimeOffset]::Parse('"+plan.DEADLINE+"')\nif([DateTimeOffset]::UtcNow -ge $end){throw 'Remaining baseline window closed'}\n$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+raw+"'))|ConvertFrom-Json)\n"
    source=prefix+files['common.ps1']+"\n$null=Read-Remaining02Handoff '"+handoff['recordSha256']+"'\n"
    for root in (r'C:\ProgramData\AzureLocalBox\ComputeCapacity-20261108-01',r'C:\ProgramData\AzureLocalBox\ComputeCapacity-R2-20261108-01',r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261109-01',plan.ROOT):
        source+="if(Test-Path '"+root+"'){throw 'Forbidden legacy/new03 history exists; no baseline admission'}\n"
    source+="$snapshot=Read-ComputeSnapshot $true\n$wanted=ConvertFrom-Json '"+json.dumps(first['beforeProfiles'],sort_keys=True,separators=(',',':'))+"'\n$states=ConvertFrom-Json '"+json.dumps(first['beforeStates'],sort_keys=True,separators=(',',':'))+"'\nforeach($g in $snapshot.guestsStatic){$p=$wanted.PSObject.Properties[$g.name].Value;if($null -eq $p -or $g.cpu -ne $p.cpu -or $g.memory -ne $p.memory -or $snapshot.states[$g.name] -cne $states.PSObject.Properties[$g.name].Value){throw 'Actual suffix profile/power differs'}}\nAssert-ComputeEqual $snapshot.clusterStatic $plan.baseline.clusterStatic 'Original pool/mirror/CSV/infrastructure identities changed'\n"
    source+=r"""
Assert-ComputeEqual $snapshot.hostStatic $plan.baseline.hostStatic 'Outer host/storage/network identity drift'
Assert-ComputeEqual $snapshot.volumesStatic $plan.baseline.volumesStatic 'Volume identity drift'
Assert-Compute (@($snapshot.guestsStatic).Count -eq 4) 'Exactly four original guests required'
foreach($g in $snapshot.guestsStatic){
 $old=@($plan.baseline.guestsStatic|Where-Object name -CEQ $g.name)
 Assert-Compute ($old.Count -eq 1) 'Original guest identity missing'
 $copy=@{};foreach($k in $g.Keys){$copy[$k]=$g[$k]};$copy.cpu=$old[0].cpu;$copy.memory=$old[0].memory
 Assert-ComputeEqual $copy $old[0] 'Original non-profile guest identity drift'
}
foreach($v in $snapshot.volumes){
 $b=$plan.admission.volumeBudgets.PSObject.Properties[$v.letter].Value
 Assert-Compute ($null -ne $b -and $v.health -ceq 'Healthy' -and $v.free -ge $b.freeFloorBytes -and ($b.maximumVhdBytes+$b.runtimeBytes+$b.metadataBytes+$b.freeFloorBytes) -le $v.size) 'Unchanged volume growth/runtime reserve failed'
}
$c=$snapshot.hostCapacity
Assert-Compute ($c.logicalProcessors -eq 64 -and $c.physicalCores -eq 32 -and $c.memoryBytes -ge 500GB -and $c.freeMemoryBytes -ge 32GB -and $c.numa.Count -gt 0 -and ($c.numa|ForEach-Object {[int]$_.logicalProcessors}|Measure-Object -Sum).Sum -eq 64 -and (Get-VMHost).NumaSpanningEnabled) 'Actual E64/NUMA/outer reserve failed'
Assert-Compute ($snapshot.clusterHealth.physicalFreeBytes -ge ($plan.admission.requiredPhysicalFreeBytes+$plan.admission.repairReserveBytes)) 'Unchanged physical S2D reserve failed'
"""
    if selected:
        returning=first['healthProfile']=='selected-return' or first['effect']=='guest-start'
        source+="$proof=Get-Content (Join-Path (Get-RemainingDrainRoot 'LB-NODE02') 'drain-proof-LB-NODE02.json') -Raw|ConvertFrom-Json\nAssert-ComputeMaintenanceHealth $snapshot 'LB-NODE02' $proof $"+str(returning).lower()+"\n"
    else:source+="$h=$snapshot.clusterHealth\nif(-not $h.allNodesUp -or -not $h.allCsvOnline -or -not $h.allMirrorsHealthy -or -not $h.poolHealthy -or $h.activeStorageJobs.Count){throw 'Strict next drain/completion requires full convergence'}\n"
    source+="$peer=Get-ProfileMocPeer $entry.node $snapshot\n$moc=Read-ProfileMoc $peer\nAssert-ProfileMocMembership $moc (ConvertFrom-Json '"+json.dumps(first['beforeMocMembers'])+"') $plan.mocContract\nif([DateTimeOffset]::UtcNow -ge $end){throw 'Remaining baseline window closed after reads'}\n@{status='complete';mutationPerformed=$false;operationId='"+plan.OPERATION_ID+"';predecessorHandoffSha256='"+handoff['recordSha256']+"';snapshot=$snapshot;mocObservation=$moc;numaSpanningEnabled=(Get-VMHost).NumaSpanningEnabled;atUtc=[datetime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 40 -Compress\n"
    return source


if __name__=='__main__':
    print(json.dumps({'unsealedPlan':plan.candidate(),'files':render(),'executionGo':False},indent=2))
