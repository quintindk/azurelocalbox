"""Bounded three-stage03 operator. Import/assemble are offline. run() requires explicit parent callbacks."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_offconfig_execution',R/'execution.py');code=importlib.util.module_from_spec(spec);spec.loader.exec_module(code)
old=code.old
require=old.require
sha=old.sha
canonical=old.canonical
stamp=old.stamp
fresh=old.fresh

def load_manifest(stage):
 path=old.EXECUTION/('offconfig-assembly-'+stage+'.json')
 return json.loads(path.read_bytes())

def verified_receipt(path,accepted_sha,source_sha):
 raw=path.read_bytes();require(old.plan.pin(accepted_sha) and sha(raw)==accepted_sha,'Parent-accepted actual receipt hash differs')
 r=json.loads(raw)
 require(r.get('status')=='complete' and r.get('sshExitCode')==0 and r.get('strictPinnedHostKey') is True and r.get('passwordAuthentication') is False and r.get('loopbackOnly') is True and r.get('renderedSourceSha256')==source_sha,'Actual GET failed, transport unqualified or exact new source differs')
 return r

def check_new_worker(result,manifest):
 require(result.get('observedStage')==manifest['stage'] and result.get('actualWorkerSha256')==manifest['workerSha256'],'Not the actual newly compiled previous worker')
 w=result['worker'];stage=manifest['stage'];expected=manifest['workerSha256']
 for k,v in {'operationId':old.plan.OPERATION_ID,'planSha256':old.PLAN_SHA,'sourceCommit':old.SOURCE,'stage':stage,'key':stage,'offconfigDecisionSha256':code.DECISION,'offconfigSourceContractSha256':manifest['reviewedSourceContractSha256'],'offconfigCompilerSourceCommit':manifest['compilerSourceCommit'],'executingWorkerSourceSha256':expected,'currentOfflineOwnerProven':False,'exactStorageIdentities':False}.items():require(w.get(k)==v,'Actual new worker provenance differs: '+k)
 require(w['sourceSha256'].lower()==expected and w['pid']>0 and stamp(w['processStartedUtc']) and w['phase']=='returned' and w['rpcInvoked'] is True and w.get('rpcReturned') is True and w['outcome'] in ('rpc-returned-await-independent-observation','rpc-returned-postread-failed-await-independent-observation'),'Original actual new worker has unknown/unreturned RPC')
 # Manifest hashes refer to the NEW source bytes, never reconstructed old worker bytes.
 for suffix in ('worker.ps1','observe.ps1'):
  name=stage+'.'+suffix;published=old.ROOT/'scripts/rolling-profile-live-20261110-03'/name
  require(sha(published.read_bytes())==manifest['artifacts'][name]['sha256'],'Actual published new source differs: '+name)
 return w

def validate_facts(v,e,stage,now):
 require(e.get('requestedStage')==stage and e.get('currentOfflineOwnerProven') is False and e.get('exactStorageIdentities') is False and e.get('parentQualificationDecisionSha256')==code.DECISION and e.get('nativeRequestedStageHistoryAbsent') is True,'Explicit limited evidence/remote unused-stage binding missing')
 require(e.get('hostStaticPasses')==1 and e.get('survivorClusterPasses')==1 and e.get('inventoryInsideMocReader')==0,'Unexpected qualification read boundary')
 rows=v['transitionContract']['stages'];row=rows[stage];s=e['hostSnapshot'];cluster=e['cluster'];h=cluster['health'];m=cluster['mocObservation']
 times={'readStartedAtUtc':e['readStartedAtUtc'],'hostAtUtc':s['atUtc'],'survivorAtUtc':cluster['atUtc'],'mocAtUtc':m['atUtc'],'qualificationAtUtc':e['atUtc']}
 for t in times.values():fresh(t,now)
 for key in ('hostStatic','volumesStatic'):require(s[key]==v['baseline'][key],'Actual outer host/volume identity drift')
 require(s['mutationPerformed'] is False and len(s['guestsStatic'])==4 and s['states']==row['beforeStates'],'Actual exact current VM state differs')
 profiles={}
 for g in s['guestsStatic']:
  b=next(x for x in v['baseline']['guestsStatic'] if x['name']==g['name'])
  require({**g,'cpu':b['cpu'],'memory':b['memory']}==b,'Actual original VM/VHD/NIC/security static drift')
  profiles[g['name']]={'cpu':g['cpu'],'memory':g['memory']}
 require(profiles==row['beforeProfiles'] and s['states']['LB-NODE02']=='Off','Exact Off transition differs, or effect was already applied')
 cap=s['hostCapacity'];require(cap['logicalProcessors']==64 and cap['physicalCores']==32 and cap['memoryBytes']>=500*old.plan.GIB and cap['freeMemoryBytes']>=32*old.plan.GIB and sum(x['logicalProcessors'] for x in cap['numa'])==64,'Actual E64/NUMA/outer memory reserve failed')
 if stage=='guest-start-LB-NODE02':require(cap['freeMemoryBytes']>=128*old.plan.GIB,'Actual compensating-start availability plus32GiB reserve failed')
 require(len(s['volumes'])==4 and {x['letter'] for x in s['volumes']}==set(v['admission']['volumeBudgets']),'Actual volume coverage differs')
 for vol in s['volumes']:
  b=v['admission']['volumeBudgets'][vol['letter']];require(vol['health']=='Healthy' and vol['free']>=b['freeFloorBytes'] and sum(b[k] for k in ('maximumVhdBytes','runtimeBytes','metadataBytes','freeFloorBytes'))<=vol['size'],'Actual original volume/runtime reserve failed')
 expected_static={k:v['baseline']['clusterStatic'][k] for k in ('name','poolId','poolSize','virtualDisks','csv')}
 require(cluster['static']==expected_static,'Actual pool/mirror/CSV static identity drift')
 require(h['nodeStates']==[{'name':'LB-NODE01','state':'Up'},{'name':'LB-NODE02','state':'Down'},{'name':'LB-NODE03','state':'Up'}],'Actual survivor/selected node state differs')
 require(h['quorumType']=='Majority' and h['witness'] is None and len(h['csvStates'])==4 and all(x['state']=='Online' and x['accessible'] is True for x in h['csvStates']),'Actual quorum/CSV accessibility failure')
 expected_unresolved=json.loads((R/'unresolved-storage-identities.json').read_bytes());actual=e['unresolvedStorageIdentities']
 require(len(actual)==8 and {x['UniqueId']:x for x in actual}=={x['UniqueId']:x for x in expected_unresolved},'Actual native unresolved GUID/scalar records changed; no aliases permitted')
 owners=v['transitionContract']['deviceOwners'];survivors={k:n for k,n in owners.items() if n!='LB-NODE02'}
 devices=h['devices'];known=[x for x in devices if x['owner'] is not None];unknown=[x for x in devices if x['owner'] is None]
 require(len(devices)==24 and len(known)==16 and {x['id']:x['owner'] for x in known}==survivors and {x['id'] for x in unknown}=={x['UniqueId'] for x in actual},'Exact16 known survivors plus8 unresolved native IDs required')
 for d in known:
  b=next(x for x in v['baseline']['clusterStatic']['members'] if x['id']==d['id']);require(d['size']==b['size'] and d['health']=='Healthy' and d['operational']==['OK'] and d['maintenance'] is False,'Actual known survivor identity/size/health failed')
 require(all(x['health']=='Warning' and x['operational']==['Lost Communication'] for x in unknown),'Unknown state beyond actual offline shape')
 allowed={'OK','Degraded','Incomplete','InService','In Service'}
 require(h['poolHealth'] in ('Healthy','Warning') and h['poolOperational'] and set(h['poolOperational'])<=allowed,'Actual pool degradation outside planned scope')
 require(len(h['virtualDiskStates'])==5 and all(x['copies']==3 and x['health'] in ('Healthy','Warning') and x['operational'] and set(x['operational'])<=allowed for x in h['virtualDiskStates']),'Actual mirror degradation outside planned scope')
 require(h['physicalFreeBytes']>=v['admission']['requiredPhysicalFreeBytes']+v['admission']['repairReserveBytes'],'Actual unchanged physical repair reserve failed')
 seen=set()
 for job in h['activeStorageJobs']:
  ids=job['affectedVirtualDiskIds'];require(len(ids)==1 and ids[0] in old.plan.KNOWN and ids[0] not in seen and job['name']==old.plan.KNOWN[ids[0]] and job['poolId']==v['baseline']['clusterStatic']['poolId'],'Unknown/foreign/duplicate whole-mirror repair')
  seen.add(ids[0]);require(job['state'] in (('Suspended','Running') if stage=='guest-start-LB-NODE02' else ('Suspended',)) and all(x is None or x in owners for x in job['affectedDeviceIds']),'Qv2 state/device-report predicate failed')
 require(m['qualified'] is True and m['membershipObserved'] is True and m['observerNode']=='LB-NODE01' and m['commands']==v['mocContract']['nodes']['LB-NODE01']['commands'] and sorted(m['members'])==['LB-NODE01','LB-NODE03'] and old.plan.membership_names(m,v['mocContract']['membershipIdentity'])==['LB-NODE01','LB-NODE03'],'Actual qualified peer/MOC exclusion differs')
 history=e['originalNativeHistory'];require(history and all(x['originalProcessAlive'] is False and x['record']['phase']=='returned' and x['record'].get('rpcReturned') is True for x in history),'Original native history still active/unknown')
 stop=[x for x in history if x['record']['stage']=='guest-stop-LB-NODE02'];require(len(stop)==1 and stop[0]['record']['pid']==5960 and stop[0]['sha256']=='0cde7a4c99966a8b2e560a46ffd195ce700fdeb6d03f22f649f2c6d5f6a8237c','Original successful Stop5960 changed')
 require(e['originalDrainProof']==old.initial_drain(v),'Exact original qualified eight-device drain proof changed')
 return times

def preflight(v,stage,proof,ent_path,ent_sha,reviewed_sha,code_commit,now):
 code.validate_scope(stage,reviewed_sha,code_commit)
 require(sha(canonical(v))==old.PLAN_SHA and v['executionApproval']['parentGo'] is True and now<stamp(v['executionApproval']['expiresAt'])<=stamp('2026-11-10T23:30:00+02:00'),'Original immutable03 plan/GO/bound changed or expired')
 require(proof['parentQualificationDecisionSha256']==code.DECISION and proof['reviewedSourceContractSha256']==reviewed_sha and proof['currentOfflineOwnerProven'] is False and proof['exactStorageIdentities'] is False,'Explicit limited qualification/QA flags differ')
 fresh(proof['observedAt'],now)
 ent=old.entitlement(v,ent_path,ent_sha,now)
 require(proof['entitlementObservationProvenance']==ent and proof['freshEntitlementReceiptSha256']==ent_sha and proof['entitlementObservedAtUtc']==ent['observedAtUtc'] and proof['entitlementReceiptSha256']==proof['entitlementWindowBasisReceiptSha256']==v['entitlement']['receiptSha256'],'Actual new API observation provenance differs from immutable window binding')
 return {'limitedThreeEffectPreflightAccepted':True,'canonicalGenericOwnerPreflightAccepted':False,'currentOfflineOwnerProven':False,'exactStorageIdentities':False}

def assemble(stage,receipt_path,accepted_sha,ent_path,ent_sha,reviewed_sha,code_commit,previous_manifest=None,out=None):
 code.validate_scope(stage,reviewed_sha,code_commit);v=old.load_plan();now=datetime.now(timezone.utc)
 if stage==code.STAGES[0]:expected=sha(code.base.observer(stage).encode())
 else:
  previous_manifest=previous_manifest or load_manifest(code.STAGES[code.STAGES.index(stage)-1]);expected=previous_manifest['artifacts'][previous_manifest['stage']+'.observe.ps1']['sha256']
 receipt=verified_receipt(receipt_path,accepted_sha,expected);result=receipt['result']
 require(result.get('status') in ('complete-limited-offconfig-GET','complete-offconfig-independent-observation'),'Actual shared qualification reader did not pass; no CUD eligible')
 require(result['operationId']==v['operationId'] and result['planSha256']==old.PLAN_SHA and result['mutationPerformed'] is False and result['currentOfflineOwnerProven'] is False and result['exactStorageIdentities'] is False,'Actual read operation/scope differs')
 if previous_manifest:check_new_worker(result,previous_manifest)
 e=result['evidence'];times=validate_facts(v,e,stage,now)
 if receipt.get('beganAtSast'):fresh(receipt['beganAtSast'],now);times['actualReadBeganAtSast']=receipt['beganAtSast']
 ent=old.entitlement(v,ent_path,ent_sha,now)
 proof={'parentQualificationDecisionSha256':code.DECISION,'reviewedSourceContractSha256':reviewed_sha,'compilerSourceCommit':code_commit,'observedAt':min(times.values(),key=stamp),'sourceNativeTimes':times,'acceptedQualificationReceiptSha256':accepted_sha,'actualQualificationSourceSha256':expected,'actualQualificationPublishedCommit':receipt.get('commit'),'currentOfflineOwnerProven':False,'exactStorageIdentities':False,'unresolvedStorageIdentities':e['unresolvedStorageIdentities'],'nativeRequestedStageHistoryAbsent':True,'entitlementReceiptSha256':v['entitlement']['receiptSha256'],'entitlementWindowBasisReceiptSha256':v['entitlement']['receiptSha256'],'freshEntitlementReceiptSha256':ent_sha,'entitlementObservedAtUtc':ent['observedAtUtc'],'entitlementObservationProvenance':ent,'originalCpuReservationRetainedSha256':'4d36961051caeb508ec3db2dd484308e49a02d1684175c249d3c75e7bf4c12c4','originalReservationReconciliationSha256':code.RECONCILIATION}
 preflight(v,stage,proof,ent_path,ent_sha,reviewed_sha,code_commit,now)
 compiled=code.compile_stage(stage,proof,code_commit,reviewed_sha)
 artifacts={'stage-input-'+stage+'.json':canonical({**v,'independentProof':proof}),'stage-proof-'+stage+'.json':canonical(proof),'independent-proof-'+stage+'.json':canonical(compiled['proofEnvelope']),stage+'.worker.ps1':compiled['worker'].encode(),stage+'.dispatch.ps1':compiled['dispatcher'].encode(),stage+'.observe.ps1':compiled['observer'].encode(),stage+'.supervised-dispatch.ps1':compiled['supervised'].encode()}
 output=out or old.EXECUTION;require(output.resolve()==old.EXECUTION.resolve() or output.resolve().is_relative_to(R/'TEST_ONLY'),'Output scope differs')
 manifest={'status':'compiled-source-not-native-execution','stage':stage,'planSha256':old.PLAN_SHA,'businessOperationSourceAnchor':old.SOURCE,'compilerSourceCommit':code_commit,'reviewedSourceContractSha256':reviewed_sha,'workerSha256':compiled['workerSha256'],'parentQualificationDecisionSha256':code.DECISION,'acceptedQualificationReceiptSha256':accepted_sha,'freshEntitlementReceiptSha256':ent_sha,'currentOfflineOwnerProven':False,'exactStorageIdentities':False,'artifacts':{n:{'path':str(output/n),'sha256':sha(b),'bytes':len(b)} for n,b in artifacts.items()},'nativeExecuted':False}
 artifacts['offconfig-assembly-'+stage+'.json']=json.dumps(manifest,indent=2).encode()+b'\n'
 require(not any((output/n).exists() for n in artifacts),'Original stage output/history already exists; no overwrite/rekey')
 preflight(v,stage,proof,ent_path,ent_sha,reviewed_sha,code_commit,datetime.now(timezone.utc))
 output.mkdir(parents=True,exist_ok=True)
 with (output/('offconfig-assembly-reservation-'+stage+'.json')).open('xb') as f:f.write(canonical({'stage':stage,'planSha256':old.PLAN_SHA,'originalReservationRetained':True,'sourceContract':reviewed_sha}))
 for name,b in artifacts.items():
  with (output/name).open('xb') as f:f.write(b)
 return manifest

def run(initial_qualification_receipt,accepted_sha,reviewed_sha,code_commit,refresh_entitlement,publish,accept_observation):
 """PARENT INVOCATION ONLY. Exact three effects; stop on any error or uncertainty.
 refresh_entitlement()->(actual_new_API_path,accepted_SHA), publish(manifest)->None,
 accept_observation(actual_receipt_path)->accepted_SHA are existing parent routines.
 """
 code.validate_scope(code.STAGES[0],reviewed_sha,code_commit)
 record=old.EXECUTION/'offconfig-controller-continuation.json'
 require(not record.exists(),'Original offconfig continuation audit exists; inspect it, never replay/rekey')
 # Do not repeat the original reserve-before-failed-GET problem. No continuation
 # audit is created until the initial actual GET/API facts pass and CPU source is
 # compiled create-only. This is not a new approval record or a native request.
 ent_path,ent_sha=refresh_entitlement()
 first_manifest=assemble(code.STAGES[0],Path(initial_qualification_receipt),accepted_sha,Path(ent_path),ent_sha,reviewed_sha,code_commit)
 with record.open('xb') as f:f.write(canonical({'originalCpuReservationRetainedSha256':'4d36961051caeb508ec3db2dd484308e49a02d1684175c249d3c75e7bf4c12c4','reservationReconciliationSha256':code.RECONCILIATION,'parentQualificationDecisionSha256':code.DECISION,'stages':list(code.STAGES),'sourceContract':reviewed_sha,'status':'explicit-parent-continuation-before-any-external-effect; never rekey'}))
 def transport(script,name):
  path=old.ROOT/'docs/deployment-2026-10-27'/('private-ssh-'+name+'.json');require(not path.exists(),'Original receipt exists; no replay/rekey')
  subprocess.run(['python3','-B',str(old.ROOT/'scripts/smal-private-powershell.py'),'--script',script,'--receipt',name],cwd=old.ROOT,check=True)
  return path
 receipt=Path(initial_qualification_receipt);manifest=None
 for stage in code.STAGES:
  if stage==code.STAGES[0]:manifest=first_manifest
  else:
   ent_path,ent_sha=refresh_entitlement()
   manifest=assemble(stage,receipt,accepted_sha,Path(ent_path),ent_sha,reviewed_sha,code_commit,manifest)
  publish(manifest)
  for name,item in manifest['artifacts'].items():
   if name.endswith('.ps1'):require(sha((old.ROOT/'scripts/rolling-profile-live-20261110-03'/name).read_bytes())==item['sha256'],'Actual newly published bytes differ')
  proof=json.loads((old.EXECUTION/('stage-proof-'+stage+'.json')).read_bytes());preflight(old.load_plan(),stage,proof,Path(ent_path),ent_sha,reviewed_sha,code_commit,datetime.now(timezone.utc))
  execution=transport('scripts/rolling-profile-live-20261110-03/'+stage+'.supervised-dispatch.ps1','rolling03-'+stage.lower()+'-offconfig-execute-01')
  actual=json.loads(execution.read_bytes());result=actual.get('result',{});w=result.get('terminalOriginalState') or {}
  require(actual.get('status')=='complete' and actual.get('sshExitCode')==0 and result.get('originalWorkerExited') is True and result.get('waitTimedOut') is False and result.get('workerSha256')==manifest['workerSha256'] and w.get('rpcReturned') is True and w.get('phase')=='returned' and w.get('outcome') in ('rpc-returned-await-independent-observation','rpc-returned-postread-failed-await-independent-observation'),'Native result unknown/failed/incomplete. STOP; inspect original, never replay/rekey')
  receipt=transport('scripts/rolling-profile-live-20261110-03/'+stage+'.observe.ps1','rolling03-'+stage.lower()+'-offconfig-observe-01')
  accepted_sha=accept_observation(receipt)
  actual_read=verified_receipt(receipt,accepted_sha,manifest['artifacts'][stage+'.observe.ps1']['sha256'])
  check_new_worker(actual_read['result'],manifest)
  if stage==code.STAGES[-1]:
   e=actual_read['result']['evidence'];require(e.get('original24VpdIdentityAndOwnershipRestored') is True and e.get('canonicalMaintenanceGuardAccepted') is True,'Original24 VPD owners/unchanged maintenance guard not restored. STOP before resume/MOC add')
 return {'status':'three-original-effects-known-returned-and-independently-observed','lastReceipt':str(receipt),'acceptedLastReceiptSha256':accepted_sha,'original24VpdOwnerAndMaintenanceGuardAccepted':True,'nextStage':'resume-LB-NODE02','nextAction':'Original resume/MOC-add remain separate original operations. No new outage or AKS until strict full health and zero jobs.','originalCpuReservationRetained':True}

def assemble_original_resume(receipt_path,accepted_sha,ent_path,ent_sha):
 """Offline bridge only: validate actual NEW start observer, then UNCHANGED Resume factory.

 Does not run/modify Resume, MOC-add or their predicates. A remaining GUID or failed
 original canonical maintenance guard refuses before producing any Resume source.
 """
 v=old.load_plan();manifest=load_manifest('guest-start-LB-NODE02');source=manifest['artifacts']['guest-start-LB-NODE02.observe.ps1']['sha256']
 receipt=verified_receipt(receipt_path,accepted_sha,source);r=receipt['result'];check_new_worker(r,manifest)
 e=r['evidence'];require(e.get('original24VpdIdentityAndOwnershipRestored') is True and e.get('canonicalMaintenanceGuardAccepted') is True,'Actual original24 VPD identity/owner return not proved')
 now=datetime.now(timezone.utc);s=e['hostSnapshot'];m=e['cluster']['mocObservation'];row=v['transitionContract']['stages']['resume-LB-NODE02']
 profiles=old.profiles_storage(v,s,row);context=old.health(v,s,row,e['originalDrainProof'])
 require(m['qualified'] is True and m['membershipObserved'] is True and m['observerNode']=='LB-NODE01' and m['commands']==v['mocContract']['nodes']['LB-NODE01']['commands'] and old.plan.membership_names(m,v['mocContract']['membershipIdentity'])==row['beforeMocMembers'],'Actual original MOC return context differs')
 times={'host':s['atUtc'],'moc':m['atUtc'],'observation':r['atUtc']}
 for at in times.values():fresh(at,now)
 ent=old.entitlement(v,ent_path,ent_sha,now)
 proof={'observedAt':min(times.values(),key=stamp),'sourceNativeTimes':times,'acceptedPreviousReceiptSha256':accepted_sha,'acceptedPreviousActualWorkerSha256':manifest['workerSha256'],'actualPreviousObserverSourceSha256':source,'actualPreviousObserverPublishedCommit':receipt.get('commit'),'previousStage':'guest-start-LB-NODE02','previousEffectIndependentlySettled':True,'originalOperationsReconciled':True,'originalReconciliationSha256':old.plan.RECONCILIATION['coordinatorReconciliationSha256'],'predecessorHandoffSha256':v['predecessorHandoff']['recordSha256'],'retained02RootVerified':True,'forbiddenLegacyRootsAbsent':True,'retainedRootEvidenceBasis':'Source-verified original workers and unchanged next native guards; no new root inventory asserted','exactSourcePublished':True,'localWindowsAuthorityVerified':True,'exactStorageIdentities':True,'storageIdentityProofBasis':'Actual original24 VPD IDs, per-device owners, original cluster statics and UNCHANGED canonical maintenance guard passed after start. No GUID alias mapping.','volumeGrowthBudgetsFit':True,'supportedProfilesVerified':True,'maintenanceQualificationSha256':v['maintenanceQualification']['qualified03JobsSourceSha256'],'mocContractQualified':True,'mocMembers':row['beforeMocMembers'],'beforeProfiles':profiles,'beforeStates':s['states'],'outerMemoryBytes':s['hostCapacity']['memoryBytes'],'physicalFreeBytes':s['hostCapacity']['freeMemoryBytes'],'retainedOriginalDrainProof':e['originalDrainProof'],'retainedDrainProofs':{'LB-NODE02':e['originalDrainProof']},'entitlementReceiptSha256':v['entitlement']['receiptSha256'],'entitlementWindowBasisReceiptSha256':v['entitlement']['receiptSha256'],'freshEntitlementReceiptSha256':ent_sha,'entitlementObservedAtUtc':ent['observedAtUtc'],'freshEntitlementVerified':True,'entitlementObservationProvenance':ent,**context}
 old.preflight(v,'resume-LB-NODE02',proof,ent_path,ent_sha,now)
 stage='resume-LB-NODE02';value={**v,'independentProof':proof};dispatch=old.build.capsule(value,stage,old.SOURCE,'dispatch');observe=old.build.capsule(value,stage,old.SOURCE,'observe')
 blobs={'stage-input-'+stage+'.json':canonical(value),'stage-proof-'+stage+'.json':canonical(proof),'independent-proof-'+stage+'.json':canonical(dispatch['independentProof']),stage+'.worker.ps1':dispatch['worker'].encode(),stage+'.dispatch.ps1':dispatch['dispatcher'].encode(),stage+'.observe.ps1':observe['dispatcher'].encode(),stage+'.supervised-dispatch.ps1':dispatch['supervisedDispatcher'].encode()}
 require(not any((old.EXECUTION/n).exists() for n in blobs),'Original Resume already has source/history; no overwrite/rekey')
 with (old.EXECUTION/'offconfig-original-resume-bridge.json').open('xb') as f:f.write(canonical({'actualStartReceiptSha256':accepted_sha,'actualNewStartWorkerSha256':manifest['workerSha256'],'originalResumeFactoryUnchanged':True,'planSha256':old.PLAN_SHA}))
 for n,b in blobs.items():
  with (old.EXECUTION/n).open('xb') as f:f.write(b)
 return {'stage':stage,'originalFactoryUnchanged':True,'nativeExecuted':False,'artifacts':{n:{'path':str(old.EXECUTION/n),'sha256':sha(b)} for n,b in blobs.items()}}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stage',choices=code.STAGES,required=True);p.add_argument('--qualification-receipt',type=Path,required=True);p.add_argument('--accepted-qualification-sha256',required=True);p.add_argument('--entitlement-receipt',type=Path,required=True);p.add_argument('--accepted-entitlement-sha256',required=True);p.add_argument('--reviewed-source-sha256',required=True);p.add_argument('--compiler-source-commit',required=True)
 a=p.parse_args();print(json.dumps(assemble(a.stage,a.qualification_receipt,a.accepted_qualification_sha256,a.entitlement_receipt,a.accepted_entitlement_sha256,a.reviewed_source_sha256,a.compiler_source_commit),indent=2))
