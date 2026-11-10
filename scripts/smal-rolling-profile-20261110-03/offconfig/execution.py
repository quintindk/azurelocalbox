"""Exact three-effect03 source compiler. Private, no native/Git execution."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re

R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_offconfig_compile',R/'compile.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
old=base.old
STAGES=('cpu-LB-NODE02','memory-LB-NODE02','guest-start-LB-NODE02')
DECISION='0ec7150bd3d1bba859bce60eb2ac0a2d06a2c3964311e390b722eb6181c3ec54'
RECONCILIATION='394a3c953f2ae3add3b6ce7c7023e2ede5e0953e78db54d47008e94767e70ac6'
GET_V02_SHA='30e528cd0a530d3852f8263868bcf37e01a5138ac0da6420925b443d917a7ad1'
sha=old.sha
canonical=old.canonical
require=old.require
once=old.build.replace_once

def contract_sha():
 names=('compile.py','offconfig-v03.ps1.in','offconfig-nodes-v03.ps1','offconfig-membership-v02.ps1','unresolved-storage-identities.json','execution.py','operator03.py')
 return sha(canonical({n:sha((R/n).read_bytes()) for n in names}))

def validate_scope(stage,reviewed_sha,code_commit):
 require(stage in STAGES,'Only the three original NODE02 Off stage keys are permitted')
 require(reviewed_sha==contract_sha(),'Exact implemented source contract must be parent-reviewed')
 require(re.fullmatch('[a-f0-9]{40}',code_commit) is not None and code_commit!=old.SOURCE,'Published new compiler/preflight source anchor required; not the old business ancestor')
 require(sha((R/'read-smal-rolling03-offconfig-cpu-qualification-20261110-02.ps1').read_bytes())==GET_V02_SHA,'Frozen version02 GET changed')
 raw=(old.EXECUTION/'offconfig-parent-qualification.json').read_bytes();require(sha(raw)==DECISION,'Exact existing parent scope decision changed')
 rec=(old.EXECUTION/'cpu-reservation-reconciliation.json').read_bytes();require(sha(rec)==RECONCILIATION,'Original CPU reservation reconciliation changed')
 require(sha((old.EXECUTION/'operator-step-cpu-LB-NODE02.json').read_bytes())=='4d36961051caeb508ec3db2dd484308e49a02d1684175c249d3c75e7bf4c12c4','Retained original CPU local reservation changed')

SELF_LAUNCH=r"""
function Assert-OffconfigSelfLaunch($artifacts,[string]$key){
 $root='C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-03'
 $expected=@(('worker-'+$key+'.journal-fixed-01.ps1'),('request-'+$key+'.json'),('launch-'+$key+'-returned.json'))
 Assert-Compute ((@($artifacts.Name|Sort-Object)-join '|') -ceq (@($expected|Sort-Object)-join '|')) 'OFFCONFIG: current launch has additional/missing native artifacts'
 Assert-Compute (-not(Test-Path (Join-Path $root ('worker-'+$key+'.state.json')))) 'OFFCONFIG: current stage state already exists; no replay'
 $path=Join-Path $root ('worker-'+$key+'.journal-fixed-01.ps1')
 Assert-Compute ($PSCommandPath -ceq $path -and (Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ceq $state.sourceSha256.ToLowerInvariant()) 'OFFCONFIG: actual current worker path/hash differs'
 $request=Get-Content (Join-Path $root ('request-'+$key+'.json')) -Raw|ConvertFrom-Json
 $launch=Get-Content (Join-Path $root ('launch-'+$key+'-returned.json')) -Raw|ConvertFrom-Json
 Assert-Compute ($request.operationId -ceq $plan.operationId -and $request.planSha256 -ceq $planSha -and $request.sourceCommit -ceq $sourceCommit -and $request.stage -ceq $key -and $request.key -ceq $key -and $request.independentProofSha256 -ceq $independentProofSha256 -and $request.executingWorkerSha256 -ceq $state.sourceSha256.ToLowerInvariant() -and $request.offconfigDecisionSha256 -ceq $OffconfigParentDecisionSha256 -and $request.offconfigSourceContractSha256 -ceq $OffconfigSourceContractSha256 -and $request.offconfigCompilerSourceCommit -ceq $OffconfigCompilerSourceCommit) 'OFFCONFIG: exact original create-only request/actual source binding differs'
 Assert-Compute ($launch.planSha256 -ceq $planSha -and $launch.stage -ceq $key -and $launch.key -ceq $key -and $launch.pid -eq $PID -and $launch.workerProcessStartedUtc -ceq $state.processStartedUtc -and $launch.phase -ceq 'launch-returned') 'OFFCONFIG: exact launched process/start time differs'
}
function Assert-OffconfigFreshAuthority {
 $now=[DateTimeOffset]::UtcNow
 Assert-Compute ($OffconfigProof.parentQualificationDecisionSha256 -ceq $OffconfigParentDecisionSha256 -and $OffconfigProof.reviewedSourceContractSha256 -ceq $OffconfigSourceContractSha256 -and $OffconfigProof.currentOfflineOwnerProven -eq $false -and $OffconfigProof.exactStorageIdentities -eq $false) 'OFFCONFIG: explicit limited scope/source QA/unresolved flags differ'
 Assert-Compute ($OffconfigProof.entitlementWindowBasisReceiptSha256 -ceq $plan.entitlement.receiptSha256 -and $OffconfigProof.entitlementReceiptSha256 -ceq $plan.entitlement.receiptSha256 -and $OffconfigProof.freshEntitlementReceiptSha256 -cne $plan.entitlement.receiptSha256 -and $OffconfigProof.freshEntitlementReceiptSha256 -ceq $OffconfigProof.entitlementObservationProvenance.freshEntitlementReceiptSha256) 'OFFCONFIG: actual fresh API receipt versus immutable window basis differs'
 foreach($at in @($OffconfigProof.observedAt,$OffconfigProof.entitlementObservedAtUtc)){$age=($now-[DateTimeOffset]::Parse($at)).TotalSeconds;Assert-Compute ($age -ge 0 -and $age -le 300) 'OFFCONFIG: native/API proof stale or future'}
 Assert-Compute ([DateTimeOffset]::Parse($OffconfigProof.entitlementObservationProvenance.earliestOwnerExpiryUtc) -ge [DateTimeOffset]::Parse($plan.executionApproval.expiresAt) -and $now -lt [DateTimeOffset]::Parse($plan.executionApproval.expiresAt)) 'OFFCONFIG: effective Owner/original phase window insufficient'
}
"""

def worker_functions(functions):
 begin=functions.index('function Read-OffconfigEvidence(')
 read=functions[begin:]
 read=once(read,'function Read-OffconfigEvidence(','function Read-OffconfigWorkerEvidence(')
 request_guard="  Assert-Compute (Test-Path -LiteralPath (Join-Path $root ($file.Name.Replace('request-','worker-').Replace('.json','.state.json')))) 'OFFCONFIG: original native request without known worker'"
 read=once(read,request_guard,"  if($file.Name -cne ('request-'+$requestedStage+'.json')){\n"+request_guard+"\n  }")
 read=once(read," Assert-Compute ($requestedArtifacts.Count -eq 0) 'OFFCONFIG: requested stage already has native history; no replay/rekey'",' Assert-OffconfigSelfLaunch $requestedArtifacts $requestedStage')
 return functions+'\n'+SELF_LAUNCH+'\n'+read

def return_observer_functions(functions):
 # Keep the original generic cluster/owner/maintenance rules. Remove ONLY unused
 # nested network/ARP inventory, retaining exact original nested VM static projection.
 begin=functions.index('function Read-ComputeSnapshot(');end=functions.index('\nfunction Read-ComputeDcNetwork',begin)
 src=functions[begin:end]
 net_begin=src.rfind('\n',0,src.index('network = @{'))+1
 net_end=src.rfind('\n',0,src.index('nestedVms = @(',net_begin))+1
 src=src[:net_begin]+src[net_end:]
 src=once(src,'function Read-ComputeSnapshot(','function Read-OffconfigOriginalReturnSnapshot(')
 return functions+'\n'+src

def prefix(v,stage,proof,code_commit,reviewed_sha):
 return "$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(canonical(v)).decode()+"'))|ConvertFrom-Json)\n$stage='"+stage+"'\n$effectKey=$stage\n$planSha='"+old.PLAN_SHA+"'\n$sourceCommit='"+old.SOURCE+"'\n$OffconfigCompilerSourceCommit='"+code_commit+"'\n$OffconfigSourceContractSha256='"+reviewed_sha+"'\n$OffconfigProof=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(canonical(proof)).decode()+"'))|ConvertFrom-Json)\n"

def compile_stage(stage,proof,code_commit,reviewed_sha):
 validate_scope(stage,reviewed_sha,code_commit);v,functions=base.common();templates=old.build.render()
 require(sha(canonical(v))==old.PLAN_SHA,'Immutable original03 plan changed')
 envelope={'operationPlanSha256':old.PLAN_SHA,'sourceCommit':old.SOURCE,'stage':stage,'proof':proof};proof_sha=sha(canonical(envelope))
 pre=prefix(v,stage,proof,code_commit,reviewed_sha)+"$independentProofSha256='"+proof_sha+"'\n"
 shared=worker_functions(functions);worker=templates['worker.ps1']
 worker=once(worker,"    Save-R2Worker 'preflight'","    # Fresh bounded qualification runs before this stage's first journal write.")
 start=worker.index("    $clusterRead = $entry.healthProfile")
 end=worker.index('    if ((Get-VMHost).LogicalProcessorCount',start)
 replacement="    Assert-Compute ($stage -cin @('cpu-LB-NODE02','memory-LB-NODE02','guest-start-LB-NODE02') -and $entry.node -ceq 'LB-NODE02' -and $entry.effect -cin @('cpu','memory','guest-start')) 'OFFCONFIG: outside exact three effects'\n    Assert-OffconfigFreshAuthority\n    $offEvidence=Read-OffconfigWorkerEvidence $stage\n    $before=$offEvidence.hostSnapshot\n    $state.currentOfflineOwnerProven=$false;$state.exactStorageIdentities=$false\n    $state.unresolvedStorageIdentities=$offEvidence.unresolvedStorageIdentities\n    $state.qualificationReadStartedAtUtc=$offEvidence.readStartedAtUtc;$state.qualificationReadAtUtc=$offEvidence.atUtc\n    $state.mocExecutingPeer='LB-NODE01';$state.mocTarget='LB-NODE02'\n    Save-R2Worker 'preflight'\n"
 worker=worker[:start]+replacement+worker[end:]
 worker=once(worker,"function Save-R2Worker(","$state.offconfigDecisionSha256=$OffconfigParentDecisionSha256\n$state.offconfigSourceContractSha256=$OffconfigSourceContractSha256\n$state.offconfigCompilerSourceCommit=$OffconfigCompilerSourceCommit\n$state.executingWorkerSourceSha256=$state.sourceSha256.ToLowerInvariant()\n$state.sourceCommitSemantics='Immutable original03 business/operation anchor, not publication of these modified bytes'\n$state.currentOfflineOwnerProven=$false;$state.exactStorageIdentities=$false\nfunction Save-R2Worker(")
 worker=once(worker,"    $state.rpcInvoked = $true; Save-R2Worker 'rpc-pending'","    Assert-OffconfigFreshAuthority\n    $state.rpcInvoked = $true; Save-R2Worker 'rpc-pending'")
 worker=pre+shared+'\n'+worker;worker_sha=sha(worker.encode())
 dispatcher=templates['stage.ps1']
 # Existing-root only. Never recreate/relabel original operation.json.
 begin=dispatcher.index("        } else {\n            $null = New-Item $root")
 end=dispatcher.index('        $workerFile =',begin)
 dispatcher=dispatcher[:begin]+"        } else { throw 'OFFCONFIG: original03 root absent; never recreate metadata' }\n"+dispatcher[end:]
 request_write="        Write-R2NewJson (Join-Path $root ('request-' + $stage + '.json')) $request"
 dispatcher=once(dispatcher,request_write,"        $request.executingWorkerSha256=$workerSha256.ToLowerInvariant();$request.offconfigDecisionSha256=$OffconfigParentDecisionSha256;$request.offconfigSourceContractSha256=$OffconfigSourceContractSha256;$request.offconfigCompilerSourceCommit=$OffconfigCompilerSourceCommit\n"+request_write)
 dispatcher=once(dispatcher,"pid = $p.Id; phase = 'launch-returned' }","pid = $p.Id; workerProcessStartedUtc = $p.StartTime.ToUniversalTime().ToString('o'); phase = 'launch-returned' }")
 dispatcher=pre+functions+'\n'+SELF_LAUNCH+"\nAssert-Compute ($stage -cin @('cpu-LB-NODE02','memory-LB-NODE02','guest-start-LB-NODE02')) 'OFFCONFIG: outside exact three effects'\nAssert-OffconfigFreshAuthority\n$mode='dispatch'\n$workerSha256='"+worker_sha.upper()+"'\n$workerBase64='"+base64.b64encode(worker.encode()).decode()+"'\n"+dispatcher
 observe=post_observer(stage,worker_sha,code_commit,reviewed_sha,functions,v)
 correction={'businessBaseOperationId':old.plan.ORIGIN_ID,'businessBasePlanSha256':old.plan.ORIGIN_PLAN_SHA,'businessBaseSourceCommit':old.plan.ORIGIN_COMMIT,'businessBaseWorkerSha256':old.build.BASE_WORKER_SHA,'journalCorrectionFactorySha256':old.build.JOURNAL_SHA,'invocationAttempt':'remaining03-'+stage.lower()+'-01','predecessorHandoffSha256':v['predecessorHandoff']['recordSha256'],'mocPeerCorrectionSha256':old.PINS['moc-peer.ps1.in'],'originalMocRefusalReconciliationSha256':old.plan.MOC_RECONCILIATION_SHA,'offconfigDecisionSha256':DECISION,'offconfigSourceContractSha256':reviewed_sha,'offconfigCompilerSourceCommit':code_commit,'executingWorkerSourceSha256':worker_sha,'currentOfflineOwnerProven':False,'exactStorageIdentities':False}
 binding={'operationId':v['operationId'],'planSha256':old.PLAN_SHA,'sourceCommit':old.SOURCE,'stage':stage,'remoteWorkerName':'worker-'+stage+'.journal-fixed-01.ps1','workerSha256':worker_sha,'dispatcherSha256':sha(dispatcher.encode()),'independentProofSha256':proof_sha,'correction':correction}
 template=(old.FACTORY/'supervision.ps1.in').read_text().replace(old.plan.ORIGIN_ROOT,old.plan.ROOT).replace('2026-11-10T20:00:00+02:00',old.plan.DEADLINE)
 supervised=template.replace('@@BINDING_JSON@@',canonical(binding).decode()).replace('@@DISPATCH_BASE64@@',base64.b64encode(dispatcher.encode()).decode())
 return {'worker':worker,'dispatcher':dispatcher,'observer':observe,'supervised':supervised,'workerSha256':worker_sha,'proofEnvelope':envelope,'qualificationFunctionsSha256':sha(functions.encode()),'binding':binding}

def post_observer(stage,worker_sha,code_commit,reviewed_sha,functions,v):
 next_stage={'cpu-LB-NODE02':'memory-LB-NODE02','memory-LB-NODE02':'guest-start-LB-NODE02','guest-start-LB-NODE02':None}[stage]
 pre=prefix(v,stage,{},code_commit,reviewed_sha)
 if next_stage:
  read="$evidence=Read-OffconfigEvidence '"+next_stage+"'\n$history=$evidence.originalNativeHistory\n"
 else:
  functions=return_observer_functions(functions)
  read=r"""
$entry=$plan.transitionContract.stages.PSObject.Properties['resume-LB-NODE02'].Value
$h=Read-Remaining02Handoff $plan.predecessorHandoff.recordSha256
$drain=Read-RemainingControl ('C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-02\'+$h.retainedOriginalDrainProof.file) $h.retainedOriginalDrainProof.sha256
$snapshot=Read-OffconfigOriginalReturnSnapshot $true
Assert-Compute ($snapshot.states['LB-NODE02'] -ceq 'Running') 'OFFCONFIG return: exact selected Running required'
foreach($g in $snapshot.guestsStatic){$expected=$entry.beforeProfiles.PSObject.Properties[$g.name].Value;Assert-Compute ($g.cpu -eq $expected.cpu -and $g.memory -eq $expected.memory -and $snapshot.states[$g.name] -ceq $entry.beforeStates.PSObject.Properties[$g.name].Value) 'OFFCONFIG return: target profile/state differs'}
# UNCHANGED canonical guard requires actual original24 VPD IDs, owners and known maintenance.
Assert-ComputeMaintenanceHealth $snapshot 'LB-NODE02' $drain $true
$moc=Read-ProfileMoc 'LB-NODE01'
Assert-OffconfigMocMembershipV02 $moc
$statePath='C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-03\worker-guest-start-LB-NODE02.state.json'
$s=Get-Content -LiteralPath $statePath -Raw|ConvertFrom-Json
$p=Get-Process -Id $s.pid -ErrorAction SilentlyContinue
Assert-Compute ($s.pid -gt 0 -and $s.processStartedUtc -and -not($p -and $p.StartTime.ToUniversalTime().ToString('o') -ceq $s.processStartedUtc)) 'OFFCONFIG return: original start worker active/unknown'
$history=@(@{record=$s;originalProcessAlive=$false;sha256=(Get-FileHash $statePath).Hash.ToLowerInvariant()})
$evidence=@{requestedStage='resume-LB-NODE02';hostSnapshot=$snapshot;cluster=@{mocObservation=$moc;atUtc=$moc.atUtc};originalDrainProof=$drain;originalNativeHistory=$history;original24VpdIdentityAndOwnershipRestored=$true;canonicalMaintenanceGuardAccepted=$true;readStartedAtUtc=$snapshot.atUtc;atUtc=[datetime]::UtcNow.ToString('o')}
"""
 tail="\n$rows=@($history|Where-Object {$_.record.stage -ceq $stage})\nAssert-Compute ($rows.Count -eq 1) 'OFFCONFIG observer: exact original stage state missing'\n$actual=$rows[0].record\n$path='C:\\ProgramData\\AzureLocalBox\\FoundationProfile-20261110-03\\worker-'+$stage+'.journal-fixed-01.ps1'\n"
 # Windows path literals contain single backslashes, not escape processing.
 tail=tail.replace(r'C:\\ProgramData\\AzureLocalBox\\FoundationProfile',r'C:\ProgramData\AzureLocalBox\FoundationProfile').replace(r'20261110-03\\worker-',r'20261110-03\worker-')
 tail+="Assert-Compute ((Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ceq '"+worker_sha+"' -and $actual.sourceSha256.ToLowerInvariant() -ceq '"+worker_sha+"' -and $actual.executingWorkerSourceSha256 -ceq '"+worker_sha+"' -and $actual.offconfigDecisionSha256 -ceq '"+DECISION+"' -and $actual.offconfigSourceContractSha256 -ceq $OffconfigSourceContractSha256 -and $actual.offconfigCompilerSourceCommit -ceq $OffconfigCompilerSourceCommit -and $actual.operationId -ceq $plan.operationId -and $actual.planSha256 -ceq $planSha -and $actual.sourceCommit -ceq $sourceCommit -and $actual.stage -ceq $stage -and $actual.key -ceq $stage -and $actual.phase -ceq 'returned' -and $actual.rpcReturned -eq $true -and $actual.outcome -cin @('rpc-returned-await-independent-observation','rpc-returned-postread-failed-await-independent-observation') -and $rows[0].originalProcessAlive -eq $false) 'OFFCONFIG observer: actual new worker hash/provenance/known return differs'\n@{status='complete-offconfig-independent-observation';mutationPerformed=$false;operationId=$plan.operationId;planSha256=$planSha;observedStage=$stage;actualWorkerSha256='"+worker_sha+"';offconfigCompilerSourceCommit=$OffconfigCompilerSourceCommit;offconfigSourceContractSha256=$OffconfigSourceContractSha256;currentOfflineOwnerProven=$false;exactStorageIdentities=$false;worker=$actual;evidence=$evidence;atUtc=[datetime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 60 -Compress\n"
 read_bound="\nAssert-Compute ([DateTimeOffset]::UtcNow -lt [DateTimeOffset]::Parse($plan.executionApproval.expiresAt)) 'OFFCONFIG observer: original read bound closed'\n"
 return pre+functions+read_bound+read+read_bound+tail
