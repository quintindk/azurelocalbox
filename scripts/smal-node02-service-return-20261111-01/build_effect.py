"""One dated MOC restoration, using the reviewed one-effect writer and reader. No native calls."""
import argparse,base64,hashlib,importlib.util,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_morning_read',R/'build_read.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
old=reader.old;ret=old.ret
sha=old.sha;canonical=old.canonical;require=old.require
OP='smal-node02-service-return-20261111-01';ROOT=r'C:\ProgramData\AzureLocalBox\ServiceReturn-20261111-01';BOUND='2026-11-11T15:20:00+02:00'
BOUNDARY='d2cf34d16f655010eb988b4d91bc30470fc5ee6f24e7a3b0309b220852687e0d'

def contract_sha():return sha(canonical({n:sha((R/n).read_bytes()) for n in ('build_read.py','build_effect.py')}))
def candidate():
 return {'operationId':OP,'root':ROOT,'hardStopSast':BOUND,'sourceReviewed':False,'reviewedSourceSha256':None,'sourceCommit':None,'parentSelectionSha256':None,'currentProtectionDecisionSha256':None,'acceptedCurrentProtectorHashes':None,'executionApproval':{'parentGo':False,'expiresAt':None},'nativeEffectsApproved':False,'acceptedReadReceiptSha256':None,'acceptedReadObservedAtUtc':None,'controllerClosure':None,'entitlement':None,'remainingBusinessStages':['moc-add-LB-NODE02'],'original03Adjudications':[],'old03DeadlineUnchanged':'2026-11-10T23:30:00+02:00','original03BoundaryCloseSha256':BOUNDARY,'noOutageResizePowerTpmKeyStorageOrAksAuthority':True}

def effect(p):
 require(p['operationId']==OP and p['root']==ROOT and p['hardStopSast']==BOUND and p['reviewedSourceSha256']==contract_sha() and p['sourceReviewed'] is True,'Exact dated source QA/scope required')
 require(p['executionApproval']['parentGo'] is True and p['nativeEffectsApproved'] is True and ret.old.stamp(p['executionApproval']['expiresAt'])<=ret.old.stamp(BOUND),'Current new dated GO required')
 require(re.fullmatch('[a-f0-9]{40}',p['sourceCommit'] or '') and re.fullmatch('[a-f0-9]{64}',p['currentProtectionDecisionSha256'] or '') and p['parentSelectionSha256']==p['currentProtectionDecisionSha256'] and p['currentProtectionDecisionSha256'] not in ('34342a7b787b40674257d3541e343aa9ded3dc8dfa19a6f029d7b60a8dea748f','760c52bc70211d0819671bd5c8ed05a1e20fc1119652a45ec204294c444573f5'),'NEW dated engineering/protection decision required; old decisions are reference only')
 now=datetime.now(timezone.utc);require(now<ret.old.stamp(p['executionApproval']['expiresAt']),'New dated window expired')
 for at in (p['acceptedReadObservedAtUtc'],p['entitlement']['observedAtUtc']):ret.old.fresh(at,now)
 require(set(p['acceptedCurrentProtectorHashes'])==set(ret.old.plan.IDS) and all(re.fullmatch('[A-Fa-f0-9]{64}',x) for x in p['acceptedCurrentProtectorHashes'].values()),'Explicit current four-VM fingerprint projection required')
 require(p['controllerClosure']['actualExitReceiptSha256']==BOUNDARY and p['controllerClosure']['originalControllerAbsent'] is True and p['controllerClosure']['executionReturned'] is True,'Exact known original controller closure required')
 require(ret.old.stamp(p['entitlement']['earliestOwnerExpiry'])>=ret.old.stamp(p['executionApproval']['expiresAt']),'Actual fresh Owner shorter than new GO')
 read=reader.build();read=read[:read.index('\n$o=Read-ServiceReturn04')]
 read+=r"""
function Assert-MorningAcceptedProtection($observation){
 foreach($g in $observation.hostSnapshot.guestsStatic){$expected=$phase04.acceptedCurrentProtectorHashes.PSObject.Properties[$g.name].Value;Assert-Compute ($expected -and $g.protectorHash -ceq $expected) 'New day: actual current fingerprint differs from NEW explicit acceptance'}
}
"""
 template=Path('/tmp/opencode/smal-service-return-20261110-04/moc04-effect.ps1.in').read_text()
 require(sha(template.encode())=='f4c299718a25f59746e0bd403e1a9d31dc81fbddd88929148ef99984be44dc92','Reviewed one-effect writer changed')
 template=template.replace('smal-node02-service-return-20261110-04',OP).replace(r'C:\ProgramData\AzureLocalBox\ServiceReturn-20261110-04',ROOT).replace('2026-11-10T23:40:00+02:00',BOUND)
 template=template.replace("$phase04.parentSelectionSha256 -ceq '34342a7b787b40674257d3541e343aa9ded3dc8dfa19a6f029d7b60a8dea748f'","$phase04.parentSelectionSha256 -ceq '"+p['currentProtectionDecisionSha256']+"'")
 template=template.replace('$before=Read-ServiceReturn04;Assert-MocOnlyOriginal03 $before','$before=Read-ServiceReturn04;Assert-MocOnlyOriginal03 $before;Assert-MorningAcceptedProtection $before')
 template=template.replace('$post=Read-ServiceReturn04;Assert-MocOnlyOriginal03 $post','$post=Read-ServiceReturn04;Assert-MocOnlyOriginal03 $post;Assert-MorningAcceptedProtection $post')
 root_guard=" Assert-Compute (-not(Test-Path -LiteralPath $root04)) '04: existing04 history blocks replay/rekey; inspect original'\n"
 require(template.count(root_guard)==1,'Reviewed create-only phase guard differs')
 template=template.replace(root_guard,'')
 template=template.replace(' $before=Read-ServiceReturn04;',root_guard+' $before=Read-ServiceReturn04;',1)
 # Export the already collected post-add baseline. No third full inventory is
 # needed for the next profile agent; keep all native job/identity data intact.
 final="@{status='phase04-node02-service-return-observed';operationId=$phase04.operationId;original03HistoryChanged=$false;originalProgrammeComplete=$false}|ConvertTo-Json -Compress"
 replacement="@{status='node02-service-return-observed';operationId=$phase04.operationId;original03HistoryChanged=$false;originalProgrammeComplete=$false;postReturnBaseline=$post;strictStorageConverged=($post.hostSnapshot.clusterHealth.allNodesUp -and $post.hostSnapshot.clusterHealth.allMirrorsHealthy -and $post.hostSnapshot.clusterHealth.poolHealthy -and $post.hostSnapshot.clusterHealth.allCsvOnline -and @($post.hostSnapshot.clusterHealth.activeStorageJobs).Count -eq 0);otherOutageOrAksAuthority=$false}|ConvertTo-Json -Depth 60 -Compress"
 require(template.count(final)==1,'Reviewed final result boundary differs');template=template.replace(final,replacement)
 raw=canonical(p);return template.replace('@@READ_SOURCE@@',read).replace('@@PLAN04_BASE64@@',base64.b64encode(raw).decode()).replace('@@PLAN04_SHA@@',sha(raw))

def seal(read_path,accepted_read_sha,decision_path,api_path,api_sha,source_commit,reviewed,expires):
 require(reviewed==contract_sha(),'Exact reviewed dated source contract differs');raw=read_path.read_bytes();require(sha(raw)==accepted_read_sha,'Actual parent-accepted native read changed');r=json.loads(raw)
 require(r.get('status')=='complete' and r.get('sshExitCode')==0 and r.get('strictPinnedHostKey') is True and r.get('loopbackOnly') is True and r.get('passwordAuthentication') is False and r.get('renderedSourceSha256')==sha(reader.build().encode()),'Exact passing dated native read required')
 o=r['result']['evidence'];require(o['node02State']=='Up' and o['original24VpdOwnerAndMaintenanceGuardAccepted'] is True,'Actual service-return native health missing')
 if o['canonicalMocMembers']==['LB-NODE01','LB-NODE02','LB-NODE03']:return None
 require(o['canonicalMocMembers']==['LB-NODE01','LB-NODE03'],'Exact MOC exclusion required');ret.old.fresh(o['atUtc'],datetime.now(timezone.utc))
 d_raw=decision_path.read_bytes();d=json.loads(d_raw)
 require(d['operationId']==OP and d['hardStopSast']==BOUND and d['acceptedCurrentProtectionByCoordinator'] is True and d['acceptedNativeReadReceiptSha256']==accepted_read_sha and d['original03BoundaryCloseSha256']==BOUNDARY,'Actual NEW dated engineering/current-protection acceptance missing')
 fingerprints={g['name']:g['protectorHash'] for g in o['hostSnapshot']['guestsStatic']};require(d['acceptedCurrentProtectorHashes']==fingerprints,'Do not relabel old fingerprints as current')
 p=candidate();p.update(sourceReviewed=True,reviewedSourceSha256=reviewed,sourceCommit=source_commit,parentSelectionSha256=sha(d_raw),currentProtectionDecisionSha256=sha(d_raw),acceptedCurrentProtectorHashes=fingerprints,acceptedReadReceiptSha256=accepted_read_sha,acceptedReadObservedAtUtc=o['atUtc'],nativeEffectsApproved=True,entitlement=old.entitlement(api_path,api_sha,expires))
 p['controllerClosure']={'originalControllerAbsent':True,'executionReturned':True,'acceptedByCoordinator':True,'actualExitReceiptSha256':BOUNDARY,'observedAtUtc':o['atUtc'],'basis':'Known historical coordinator controllerReturned boundary d2cf, exclusive current lane, and FRESH actual original03 request/worker process-identity absence. Not an old receipt timestamp restamp.'}
 p['executionApproval']={'parentGo':True,'expiresAt':expires};effect(p);return p

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='operation',required=True);sub.add_parser('contract');q=sub.add_parser('seal');q.add_argument('--read',type=Path,required=True);q.add_argument('--accepted-read-sha256',required=True);q.add_argument('--decision',type=Path,required=True);q.add_argument('--api',type=Path,required=True);q.add_argument('--accepted-api-sha256',required=True);q.add_argument('--source-commit',required=True);q.add_argument('--reviewed-source-sha256',required=True);q.add_argument('--expires',required=True);q.add_argument('--out',type=Path,required=True);q=sub.add_parser('compile');q.add_argument('--plan',type=Path,required=True);q.add_argument('--out',type=Path,required=True);a=parser.parse_args()
 if a.operation=='contract':print(contract_sha())
 elif a.operation=='seal':
  p=seal(a.read,a.accepted_read_sha256,a.decision,a.api,a.accepted_api_sha256,a.source_commit,a.reviewed_source_sha256,a.expires)
  if p is None:print(json.dumps({'status':'already-MOC3; no effect needed'}))
  else:
   with a.out.open('xb') as f:f.write(canonical(p))
   print(json.dumps({'newPlanSha256':sha(canonical(p)),'nativeExecuted':False}))
 else:
  text=effect(json.loads(a.plan.read_bytes()))
  with a.out.open('xb') as f:f.write(text.encode())
  print(json.dumps({'sourceSha256':sha(text.encode()),'nativeExecuted':False}))
