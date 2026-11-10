"""Narrow Resume/MOC-add compiler/operator. Original plan/raw snapshots are immutable."""
import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

R=Path(__file__).resolve().parent
path=Path('/tmp/opencode/smal-rolling03-next-stage-20261110/advance03.py');assert hashlib.sha256(path.read_bytes()).hexdigest()=='7921b6c43618369cf8bc4e948773addc2b2ff0af69961baa0c84643d9d804fba'
spec=importlib.util.spec_from_file_location('_original_return03',path);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
STAGES=('resume-LB-NODE02','moc-add-LB-NODE02')
DECISION='760c52bc70211d0819671bd5c8ed05a1e20fc1119652a45ec204294c444573f5'
NEW='F99FFFC3698A0D11DA8BD060F89228314CCEB4B67B58A218D97835F87FB1D315'
OLD='9ED1D6E402D9DA2B283F03D3986E6E69A8E79658801BFFC70A7D1CC7E4EA7FC5'
START_OBSERVER='b2da55aed844832cead9eaa03bd12a7e391fe42de081d7241791db4d5f6d9d19'
sha=old.sha;canonical=old.canonical;require=old.require;once=old.build.replace_once

def decision():
 raw=(old.EXECUTION/'poststart-protection-return-decision.json').read_bytes();require(sha(raw)==DECISION,'Exact parent engineering decision changed')
 d=json.loads(raw);require(d['stages']==list(STAGES) and d['planSha256']==old.PLAN_SHA and d['nativeGoIssued'] is False,'Only original two compensating keys covered')
 return d
def contract_sha():return sha(canonical({n:sha((R/n).read_bytes()) for n in ('return03.py','protection.ps1')}))
def shared():
 common=old.build.render()['common.ps1']
 # Same bounded original snapshot used by the accepted start observer: retain all
 # host/nested-VM/storage statics and guards, omit only unused nested network/ARP data.
 begin=common.index('function Read-ComputeSnapshot(');end=common.index('\nfunction Read-ComputeDcNetwork',begin);fn=common[begin:end]
 a=fn.rfind('\n',0,fn.index('network = @{'))+1;b=fn.rfind('\n',0,fn.index('nestedVms = @(',a))+1;fn=fn[:a]+fn[b:]
 return common[:begin]+fn+common[end:]+'\n'+(R/'protection.ps1').read_text()
def expected(v):
 x=copy.deepcopy(v['baseline']['guestsStatic']);g=next(g for g in x if g['name']=='LB-NODE02');require(g['protectorHash']==OLD,'Old sealed baseline changed');g['protectorHash']=NEW;return x
def profiles(v,s,row):
 for k in ('hostStatic','volumesStatic','clusterStatic'):require(s[k]==v['baseline'][k],'Original host/volume/storage identity drift')
 require(len(s['guestsStatic'])==4 and s['states']==row['beforeStates'],'Actual four VM states differ')
 projection=expected(v)
 for g in s['guestsStatic']:
  b=next(x for x in projection if x['name']==g['name'])
  require({k:x for k,x in g.items() if k not in ('cpu','memory')}=={k:x for k,x in b.items() if k not in ('cpu','memory')},'Actual raw nonprofile data differs from explicit expected projection')
  require({'cpu':g['cpu'],'memory':g['memory']}==row['beforeProfiles'][g['name']],'Actual stage CPU/memory differs')
 cap=s['hostCapacity'];require(cap['logicalProcessors']==64 and cap['physicalCores']==32 and cap['memoryBytes']>=500*old.plan.GIB and cap['freeMemoryBytes']>=32*old.plan.GIB,'Actual host/outer memory reserve failed')
 for vol in s['volumes']:
  b=v['admission']['volumeBudgets'][vol['letter']];require(vol['health']=='Healthy' and vol['free']>=b['freeFloorBytes'] and sum(b[k] for k in ('maximumVhdBytes','runtimeBytes','metadataBytes','freeFloorBytes'))<=vol['size'],'Original volume/runtime reserves failed')
 return row['beforeProfiles']

def pre(v,stage,proof,code_commit,reviewed):
 decision();require(stage in STAGES and reviewed==contract_sha() and re.fullmatch('[a-f0-9]{40}',code_commit) and code_commit!=old.SOURCE,'Exact reviewed new overlay source and limited key required')
 return "$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(canonical(v)).decode()+"'))|ConvertFrom-Json)\n$planSha='"+old.PLAN_SHA+"'\n$sourceCommit='"+old.SOURCE+"'\n$stage='"+stage+"'\n$effectKey=$stage\n$ProtectionOverlaySourceCommit='"+code_commit+"'\n$ProtectionOverlaySha256='"+reviewed+"'\n$ProtectionProof=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(canonical(proof)).decode()+"'))|ConvertFrom-Json)\n"

def initial_get():
 decision();v=old.load_plan();raw=(R/'reference/original-start.observe.ps1').read_bytes();require(sha(raw)==START_OBSERVER,'Exact actual start observer changed')
 text=raw.decode();needle='|ConvertTo-Json -Depth 60 -Compress';cut=text.rfind(needle);require(cut>=0 and text[cut+len(needle):]=='\n','Known final original GET JSON boundary differs')
 # Only final JSON is removed. Original worker hash, storage guards and all raw data remain.
 obj=text[:cut]+text[cut+len(needle):]
 helpers=shared();p="$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(canonical(v)).decode()+"'))|ConvertFrom-Json)\n$planSha='"+old.PLAN_SHA+"'\n$stage='resume-LB-NODE02'\n"
 p+=helpers+"\n$bytes=[Convert]::FromBase64String('"+base64.b64encode(obj.encode()).decode()+"')\n$output=@(& ([ScriptBlock]::Create([Text.Encoding]::UTF8.GetString($bytes))))\nAssert-Compute ($output.Count -eq 1 -and $output[0] -is [Collections.IDictionary]) 'PROTECTION: original GET object required'\n$o=$output[0];$s=$o.evidence.hostSnapshot\n$row=$plan.transitionContract.stages.'resume-LB-NODE02'\nAssert-ProtectionProfiles $s $row.beforeProfiles $row.beforeStates\n$node=@($s.guestsStatic|Where-Object name -CEQ 'LB-NODE02')[0]\n$current=Read-ProtectionCurrent $node.protectorHash\nAssert-Compute ([DateTimeOffset]::UtcNow -lt [DateTimeOffset]::Parse($plan.executionApproval.expiresAt)) 'PROTECTION: original read window closed'\n@{status='complete-protection-return-GET';mutationPerformed=$false;planSha256=$planSha;protectionDecisionSha256=$ProtectionDecisionSha256;originalObserverSha256='"+START_OBSERVER+"';observation=$o;currentProtection=$current;rawSnapshotRewritten=$false;sealedBaselineRewritten=$false;originalFingerprint='"+OLD+"';acceptedExpectedFingerprint='"+NEW+"';atUtc=[datetime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 60 -Compress\n"
 return p

def compile_stage(stage,proof,code_commit,reviewed):
 v=old.load_plan();templates=old.build.render();functions=shared();prefix=pre(v,stage,proof,code_commit,reviewed)
 # Replace only the named return path's profile comparator, never raw/baseline data.
 worker=templates['worker.ps1'];a=worker.index('function Assert-R2Profiles(');b=worker.index('$mutex =',a)
 worker=worker[:a]+"function Assert-R2Profiles($snapshot,$profiles,$states){Assert-ProtectionProfiles $snapshot $profiles $states}\n"+worker[b:]
 worker=once(worker,'function Save-R2Worker(',"$state.protectionDecisionSha256=$ProtectionDecisionSha256\n$state.protectionOverlaySha256=$ProtectionOverlaySha256\n$state.protectionOverlaySourceCommit=$ProtectionOverlaySourceCommit\n$state.actualExecutingWorkerSha256=$state.sourceSha256.ToLowerInvariant()\n$state.sourceCommitSemantics='Immutable business/operation anchor, not publication of these overlay bytes'\n$state.originalProtectorFingerprint='"+OLD+"'\n$state.acceptedExpectedProtectorFingerprint='"+NEW+"'\n$state.rawSnapshotRewritten=$false;$state.sealedBaselineRewritten=$false;$state.causeEstablished=$false\nfunction Save-R2Worker(")
 worker=once(worker,'    $before = Read-ComputeSnapshot $clusterRead',"    Assert-ProtectionAuthority\n    $before = Read-ComputeSnapshot $clusterRead\n    $node=@($before.guestsStatic|Where-Object name -CEQ 'LB-NODE02')[0]\n    $currentProtection=Read-ProtectionCurrent $node.protectorHash\n    $state.currentPublicProtection=$currentProtection\n    $state.knownOriginalStartWorkerPid=6552\n    $state.publicProtectionObservedAtUtc=$currentProtection.atUtc")
 worker=once(worker,"    $state.rpcInvoked = $true; Save-R2Worker 'rpc-pending'","    Assert-ProtectionAuthority\n    $state.rpcInvoked = $true; Save-R2Worker 'rpc-pending'")
 # Keep only the two original business bodies. No power/profile/completion branch
 # remains reachable or present in this worker's effect switch.
 rb=worker.index("            'resume' {");mb=worker.index("            { $_ -cin @('moc-remove','moc-add') } {",rb);me=worker.index("            'guest-start' {",mb)
 resume_body=worker[rb:mb];moc_body=once(worker[mb:me],"            { $_ -cin @('moc-remove','moc-add') } {","            'moc-add' {")
 sb=worker.index('        switch -CaseSensitive ($entry.effect) {');se=worker.index('\n        $state.rpcReturned = $true',sb)+1
 worker=worker[:sb]+"        switch -CaseSensitive ($entry.effect) {\n"+resume_body+moc_body+"            default { throw 'PROTECTION: no other effect permitted' }\n        }\n"+worker[se:]
 # Qualified strings only on this private two-key return path; binding comparison unchanged.
 functions=once(functions,'function Assert-ProfileMocMembership($read, [string[]]$expected, $contract) {','function Assert-OriginalProfileMocMembership($read, [string[]]$expected, $contract) {')
 functions+="\nfunction Assert-ProfileMocMembership($read,[string[]]$expected,$contract){Assert-ProtectionMoc $read $expected $contract}\n"
 worker=prefix+functions+'\n'+worker;worker_sha=sha(worker.encode())
 envelope={'operationPlanSha256':old.PLAN_SHA,'sourceCommit':old.SOURCE,'stage':stage,'proof':proof};proof_sha=sha(canonical(envelope))
 dispatch=templates['stage.ps1'];begin=dispatch.index("        } else {\n            $null = New-Item $root");end=dispatch.index('        $workerFile =',begin);dispatch=dispatch[:begin]+"        } else {throw 'PROTECTION: original03 root absent; never recreate metadata'}\n"+dispatch[end:]
 dispatch=prefix+functions+"\nAssert-ProtectionAuthority\n$mode='dispatch'\n$independentProofSha256='"+proof_sha+"'\n$workerSha256='"+worker_sha.upper()+"'\n$workerBase64='"+base64.b64encode(worker.encode()).decode()+"'\n"+dispatch
 # Original GET observer, exact new worker binding. Preserve all original reads/flags.
 observe=templates['stage.ps1'];begin=observe.index("if ($mode -ceq 'observe') {");end=observe.index("} elseif ($mode -ceq 'dispatch')",begin)
 observe=observe[begin:end]+"} else {throw 'Protection observer is GET-only'}\n"
 # Original observe identity does not claim settlement. Add current protection + expected statics before final JSON.
 needle=' | ConvertTo-Json -Depth 30 -Compress';cut=observe.rfind(needle);require(cut>=0,'Exact observer output boundary missing')
 observe=observe[:cut]+observe[cut+len(needle):]
 observer=prefix+functions+"\n$mode='observe'\n$workerSha256='"+worker_sha.upper()+"'\n"+templates['stage.ps1'][:begin]+"\n$read=@(& {\n"+observe+"\n})\nAssert-Compute ($read.Count -eq 1 -and $read[0] -is [Collections.IDictionary]) 'PROTECTION: one independent GET object required'\n$o=$read[0];$node=@($o.snapshot.guestsStatic|Where-Object name -CEQ 'LB-NODE02')[0]\n$current=Read-ProtectionCurrent $node.protectorHash\n@{status='complete-protection-return-observation';mutationPerformed=$false;protectionDecisionSha256=$ProtectionDecisionSha256;overlaySha256=$ProtectionOverlaySha256;overlaySourceCommit=$ProtectionOverlaySourceCommit;actualWorkerSha256='"+worker_sha+"';observation=$o;currentProtection=$current;atUtc=[datetime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 60 -Compress\n"
 correction={'businessBaseOperationId':old.plan.ORIGIN_ID,'businessBasePlanSha256':old.plan.ORIGIN_PLAN_SHA,'businessBaseSourceCommit':old.plan.ORIGIN_COMMIT,'businessBaseWorkerSha256':old.build.BASE_WORKER_SHA,'journalCorrectionFactorySha256':old.build.JOURNAL_SHA,'invocationAttempt':'remaining03-'+stage.lower()+'-01','predecessorHandoffSha256':v['predecessorHandoff']['recordSha256'],'mocPeerCorrectionSha256':old.PINS['moc-peer.ps1.in'],'originalMocRefusalReconciliationSha256':old.plan.MOC_RECONCILIATION_SHA,'protectionDecisionSha256':DECISION,'protectionOverlaySha256':reviewed,'protectionOverlaySourceCommit':code_commit,'actualExecutingWorkerSha256':worker_sha,'rawSnapshotRewritten':False,'sealedBaselineRewritten':False,'causeEstablished':False}
 binding={'operationId':v['operationId'],'planSha256':old.PLAN_SHA,'sourceCommit':old.SOURCE,'stage':stage,'remoteWorkerName':'worker-'+stage+'.journal-fixed-01.ps1','workerSha256':worker_sha,'dispatcherSha256':sha(dispatch.encode()),'independentProofSha256':proof_sha,'correction':correction}
 template=(old.FACTORY/'supervision.ps1.in').read_text().replace(old.plan.ORIGIN_ROOT,old.plan.ROOT).replace('2026-11-10T20:00:00+02:00',old.plan.DEADLINE)
 supervised=template.replace('@@BINDING_JSON@@',canonical(binding).decode()).replace('@@DISPATCH_BASE64@@',base64.b64encode(dispatch.encode()).decode())
 return {'worker':worker,'dispatch':dispatch,'observe':observer,'supervised-dispatch':supervised,'workerSha256':worker_sha,'envelope':envelope}

def proof_from(stage,receipt,accepted_sha,ent_path,ent_sha,reviewed,code_commit,previous=None,now=None):
 now=now or datetime.now(timezone.utc);v=old.load_plan();decision();require(stage in STAGES and reviewed==contract_sha(),'Exact reviewed two-key overlay required')
 expected_source=sha(initial_get().encode()) if stage==STAGES[0] else previous['artifacts'][STAGES[0]+'.observe.ps1']['sha256']
 require(receipt.get('status')=='complete' and receipt.get('sshExitCode')==0 and receipt.get('strictPinnedHostKey') is True and receipt.get('loopbackOnly') is True and receipt.get('passwordAuthentication') is False and receipt['renderedSourceSha256']==expected_source,'Actual source-verified passing fresh GET required')
 result=receipt['result'];require(result['protectionDecisionSha256']==DECISION,'Explicit current-protection decision missing');o=result['observation'];s=o['evidence']['hostSnapshot'] if stage==STAGES[0] else o['snapshot'];w=o['worker'];m=o['evidence']['cluster']['mocObservation'] if stage==STAGES[0] else o['mocObservation'];row=v['transitionContract']['stages'][stage]
 for at in (s['atUtc'],m['atUtc'],result['currentProtection']['atUtc'],result['atUtc']):old.fresh(at,now)
 require(w['pid']==6552 if stage==STAGES[0] else w['stage']=='resume-LB-NODE02','Exact actual predecessor differs')
 require(w['rpcReturned'] is True and w['phase']=='returned' and w['outcome'] in ('rpc-returned-await-independent-observation','rpc-returned-postread-failed-await-independent-observation'),'Unknown predecessor RPC')
 if stage==STAGES[0]:require(w['sourceSha256'].lower()=='14700c9137c3612dcd789ebc87c2133d26cc8a6cc9507ad474d262531f80e422' and o['evidence']['canonicalMaintenanceGuardAccepted'] is True,'Actual known Start6552/new source lineage differs')
 else:require(o['workerAlive'] is False and o['dispatcherAlive'] is False and o['workerSourceVerified'] is True and w['sourceSha256'].lower()==previous['workerSha256'] and w['protectionOverlaySha256']==reviewed,'Actual new Resume worker/source/dead observation differs')
 p=result['currentProtection'];require(p['protectorFingerprint']==NEW and p['tpmEnabled'] is True and p['secureBoot']=='On' and p['guardianName']=='LB-LocalGuardian','Actual accepted current public posture missing')
 names={x['property']:x for x in p['publicCertificates']};d=decision()['requiredCurrentPosture']
 require(names['SigningCertificate']['thumbprint']==d['signingCertificateThumbprint'] and names['EncryptionCertificate']['thumbprint']==d['encryptionCertificateThumbprint'] and all(x['currentlyWithinValidity'] is True for x in names.values()),'Actual accepted public certificates differ')
 before=profiles(v,s,row);context=old.health(v,s,row,old.initial_drain(v));require(m['qualified'] is True and m['membershipObserved'] is True and m['commands']==v['mocContract']['nodes']['LB-NODE01']['commands'] and old.plan.membership_names(m,v['mocContract']['membershipIdentity'])==row['beforeMocMembers'],'Original MOC contract/membership differs')
 ent=old.entitlement(v,ent_path,ent_sha,now);times=[s['atUtc'],m['atUtc'],p['atUtc'],result['atUtc']]
 proof={'protectionDecisionSha256':DECISION,'reviewedOverlaySha256':reviewed,'acceptedPreviousReceiptSha256':accepted_sha,'acceptedPreviousActualWorkerSha256':w['sourceSha256'].lower(),'actualPreviousPublishedObserverSourceSha256':receipt['renderedSourceSha256'],'previousStage':row['previousStage'],'previousEffectIndependentlySettled':True,'observedAt':min(times,key=old.stamp),'currentPublicProtection':p,'originalProtectorFingerprint':OLD,'acceptedExpectedProtectorFingerprint':NEW,'acceptedExpectedProjectionSha256':sha(canonical(expected(v))),'rawSnapshotRewritten':False,'sealedBaselineRewritten':False,'causeEstablished':False,'allOtherOriginalVmStaticsVerified':True,'originalOperationsReconciled':True,'originalReconciliationSha256':old.plan.RECONCILIATION['coordinatorReconciliationSha256'],'predecessorHandoffSha256':v['predecessorHandoff']['recordSha256'],'retained02RootVerified':True,'forbiddenLegacyRootsAbsent':True,'exactSourcePublished':True,'localWindowsAuthorityVerified':True,'exactStorageIdentities':True,'volumeGrowthBudgetsFit':True,'supportedProfilesVerified':True,'maintenanceQualificationSha256':v['maintenanceQualification']['qualified03JobsSourceSha256'],'mocContractQualified':True,'mocMembers':row['beforeMocMembers'],'beforeProfiles':before,'beforeStates':s['states'],'outerMemoryBytes':s['hostCapacity']['memoryBytes'],'physicalFreeBytes':s['hostCapacity']['freeMemoryBytes'],'retainedOriginalDrainProof':old.initial_drain(v),'retainedDrainProofs':{'LB-NODE02':old.initial_drain(v)},'entitlementReceiptSha256':v['entitlement']['receiptSha256'],'entitlementWindowBasisReceiptSha256':v['entitlement']['receiptSha256'],'freshEntitlementReceiptSha256':ent_sha,'entitlementObservedAtUtc':ent['observedAtUtc'],'freshEntitlementVerified':True,'entitlementObservationProvenance':ent,**context}
 old.preflight(v,stage,proof,ent_path,ent_sha,now)
 return proof

def assemble(stage,receipt_path,accepted_sha,ent_path,ent_sha,reviewed,code_commit):
 v=old.load_plan();raw=receipt_path.read_bytes();require(sha(raw)==accepted_sha,'Parent-accepted exact current GET SHA differs');previous=json.loads((old.EXECUTION/'protection-return-assembly-resume-LB-NODE02.json').read_bytes()) if stage==STAGES[1] else None
 proof=proof_from(stage,json.loads(raw),accepted_sha,ent_path,ent_sha,reviewed,code_commit,previous);caps=compile_stage(stage,proof,code_commit,reviewed)
 blobs={'stage-input-'+stage+'.json':canonical({**v,'independentProof':proof}),'stage-proof-'+stage+'.json':canonical(proof),'independent-proof-'+stage+'.json':canonical(caps['envelope'])}
 for kind in ('worker','dispatch','observe','supervised-dispatch'):blobs[stage+'.'+kind+'.ps1']=caps[kind].encode()
 manifest={'stage':stage,'planSha256':old.PLAN_SHA,'decisionSha256':DECISION,'overlaySourceCommit':code_commit,'overlaySha256':reviewed,'workerSha256':caps['workerSha256'],'nativeExecuted':False,'artifacts':{n:{'path':str(old.EXECUTION/n),'sha256':sha(b)} for n,b in blobs.items()}}
 blobs['protection-return-assembly-'+stage+'.json']=json.dumps(manifest,indent=2).encode()+b'\n';require(not any((old.EXECUTION/n).exists() for n in blobs),'Original key already has source/history; no overwrite/rekey')
 with (old.EXECUTION/('protection-return-reservation-'+stage+'.json')).open('xb') as f:f.write(canonical({'stage':stage,'decision':DECISION,'acceptedActualReceipt':accepted_sha}))
 for n,b in blobs.items():
  with (old.EXECUTION/n).open('xb') as f:f.write(b)
 return manifest

def run(receipt,accepted_sha,reviewed,code_commit,refresh_entitlement,publish,accept_observation):
 """Explicit parent invocation only. Existing transport; no new approval workflow."""
 current=Path(receipt)
 for stage in STAGES:
  ent_path,ent_sha=refresh_entitlement();manifest=assemble(stage,current,accepted_sha,Path(ent_path),ent_sha,reviewed,code_commit);publish(manifest)
  for name,item in manifest['artifacts'].items():
   if name.endswith('.ps1'):require(sha((old.ROOT/'scripts/rolling-profile-live-20261110-03'/name).read_bytes())==item['sha256'],'Actual published new source differs')
  def transport(kind):
   name='rolling03-'+stage.lower()+'-protection-'+kind+'-01';out=old.ROOT/'docs/deployment-2026-10-27'/('private-ssh-'+name+'.json');require(not out.exists(),'Original receipt exists; no replay/rekey')
   subprocess.run(['python3','-B',str(old.ROOT/'scripts/smal-private-powershell.py'),'--script','scripts/rolling-profile-live-20261110-03/'+stage+'.'+('supervised-dispatch' if kind=='execute' else 'observe')+'.ps1','--receipt',name],cwd=old.ROOT,check=True);return out
  actual=json.loads(transport('execute').read_bytes());w=actual.get('result',{}).get('terminalOriginalState') or {};require(actual.get('status')=='complete' and actual.get('sshExitCode')==0 and w.get('rpcReturned') is True and w.get('phase')=='returned' and w.get('sourceSha256','').lower()==manifest['workerSha256'],'Unknown/failed result; STOP, no replay')
  current=transport('observe');accepted_sha=accept_observation(current);read=json.loads(current.read_bytes());require(sha(current.read_bytes())==accepted_sha and read['status']=='complete' and read['sshExitCode']==0 and read['renderedSourceSha256']==manifest['artifacts'][stage+'.observe.ps1']['sha256'],'Exact new independent observer failed')
  o=read['result']['observation'];require(o['workerAlive'] is False and o['dispatcherAlive'] is False and o['worker']['rpcReturned'] is True and o['worker']['sourceSha256'].lower()==manifest['workerSha256'],'Actual new worker not independently dead/returned')
  v=old.load_plan();row=v['transitionContract']['stages'][stage];s=o['snapshot'];m=o['mocObservation'];profiles(v,s,row);old.health(v,s,row,old.initial_drain(v))
  require(m['qualified'] is True and m['membershipObserved'] is True and m['commands']==v['mocContract']['nodes']['LB-NODE01']['commands'] and old.plan.membership_names(m,v['mocContract']['membershipIdentity'])==row['afterMocMembers'] and next(x['state'] for x in s['clusterHealth']['nodeStates'] if x['name']=='LB-NODE02')=='Up','Actual Up/MOC/storage compensating postcondition absent')
 return {'status':'two-compensating-keys-independently-observed','lastReceipt':str(current),'acceptedReceiptSha256':accepted_sha,'furtherOutageOrAksAllowedByThisDecision':False,'originalBaselineAndRawDataRewritten':False}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='operation',required=True);sub.add_parser('get');q=sub.add_parser('assemble');q.add_argument('--stage',choices=STAGES,required=True);q.add_argument('--receipt',type=Path,required=True);q.add_argument('--accepted-sha256',required=True);q.add_argument('--entitlement',type=Path,required=True);q.add_argument('--accepted-entitlement-sha256',required=True);q.add_argument('--reviewed-overlay-sha256',required=True);q.add_argument('--overlay-source-commit',required=True);a=p.parse_args()
 if a.operation=='get':
  text=initial_get();path=R/'read-smal-rolling03-protection-return-20261110-01.ps1'
  with path.open('xb') as f:f.write(text.encode())
  print(json.dumps({'source':str(path),'sha256':sha(text.encode()),'nativeExecuted':False}))
 else:print(json.dumps(assemble(a.stage,a.receipt,a.accepted_sha256,a.entitlement,a.accepted_entitlement_sha256,a.reviewed_overlay_sha256,a.overlay_source_commit),indent=2))
