"""Unissued03 exact suffix. Accepted prefix and closed original failures select the boundary."""
import copy
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime,timezone

CANONICAL=Path(os.environ.get('SMAL_CANONICAL_ROOT',Path(__file__).resolve().parents[2]))
OPERATION_ID='smal-foundation-profile-20261110-03'
ROOT=r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-03'
DEADLINE='2026-11-10T23:30:00+02:00'
ORIGIN_ID='smal-foundation-profile-20261110-02'
ORIGIN_ROOT=r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-02'
ORIGIN_PLAN_SHA='c6b4dfdfb3e1170129c8d578d3a87794d9ec41142275ed69c5decc2fb6006d53'
ORIGIN_COMMIT='b8c4203c968c195786bef0f53f8d36e20f1ee8bd'
ORIGIN_OPERATION_SHA='a24e4946070b235be182a4e65767eef662902a30b9abde6431f2d6ffd5387ea5'
HANDOFF_FILE='handoff-to-FoundationProfile-20261110-03.json'
QV2_FACTORY_SHA='078ed38adf171a18dd53c46720b8933f0a3849182624f740ecbb54a686136837'
QV2_JOBS_SHA='363b261eec83c2e9ea9f4308c2a3e1f1c2614cab421777b2686b583cea632255'
QUALIFIED_HELPER_SHA='456d86c94fba7653f38165f32e5056dff49f586be9adaedfb957c86314726e3b'
MOC_RECONCILIATION_SHA='15ece71929d9e409bcb7c4b8177f05d38aa5038bfcb3df047d5422a9d86567ac'
MOC_SOURCE_RECEIPT_SHA='5632b5841b09ad0db0a9d9e586c4ec6c5ea6aa6dfb11a1f53d23926669a439ad'
MOC_REFUSAL='refused-before-node-offboarding-by-mandatory-same-node-guard'
MOC_PEERS={'LB-NODE02':'LB-NODE01','LB-NODE03':'LB-NODE01','LB-NODE01':'LB-NODE02'}
RECONCILIATION={'coordinatorReconciliationSha256':'00b33d1c8301f7ba76084d017dd283bcb271751d1c05c8fb4e638061068b8426','originalOperationId':'smal-foundation-profile-20261109-01','originalPlanSha256':'a778a5867740c0ea7de46f84f0cd4099eea27f4ba945364284ccb583a2d32b3a','loaderCleanupReceiptSha256':'6aa5e017cee9fe9a74741d795dabb699ff306eccc582cbed81cb23819270065a','independentStateReceiptSha256':'8d8030f5c2684e7965d57b9a4a95c33d26c8c1bc0af63682b600177239f1fcf7','originalDisposition':'loader-terminated-before-any-observed-durable-dispatch-or-worker-launch'}
_path=CANONICAL/'scripts/smal-rolling-profile-20261109/plan.py';_raw=_path.read_bytes()
if hashlib.sha256(_raw).hexdigest()!='c445509b9da307de2192ee25ea847be5d2a835415f32ac308d8ea4a55c4084d1':raise ValueError('Accepted business-plan source changed')
_source=_raw.decode().replace('smal-foundation-profile-20261109-01',OPERATION_ID).replace('2026-11-10T15:20:00+02:00',DEADLINE).replace("proof['retainedRootsAbsent']","proof['forbiddenLegacyRootsAbsent']")
exec(compile(_source[:_source.index("if __name__=='__main__':")],str(_path),'exec'),globals())
_whole_stages=stages;_base_candidate=candidate;_base_preflight=execution_preflight
ALL_KEYS=tuple(_whole_stages());NODE02_PREFIX=ALL_KEYS[:8]
KNOWN={'D82EEC019A25474789543A1796B552BB':'UserStorage_1-Repair','97F0D5071BB7314E9F51102237F77085':'ClusterPerformanceHistory-Repair','4C06845FA8C574499A937BD3EB57736A':'UserStorage_2-Repair','7C7DA96B2870124CADF176559F3F64F7':'UserStorage_3-Repair','9E5467C0BAC8834987723430C063E2C3':'Infrastructure_1-Repair'}
def pin(v):return isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def boundary(record):
    done=record.get('completedPrefix')
    require(isinstance(done,list) and 1<=len(done)<=8 and done==list(ALL_KEYS[:len(done)]),'Exact nonempty contiguous accepted NODE02 prefix required')
    return len(done)
def preview_stages(count):
    require(isinstance(count,int) and 1<=count<=8,'Only actual accepted NODE02 prefix lengths1..8 are supported')
    rows={k:copy.deepcopy(_whole_stages()[k]) for k in ALL_KEYS[count:]};first=next(iter(rows));rows[first]['previousStage']=None;rows[first]['settledPredecessorOperationStage']=ALL_KEYS[count-1]
    return rows
def stages(record=None):return {} if record is None else preview_stages(boundary(record))
def expected_initial_profiles(record):return copy.deepcopy(next(iter(preview_stages(boundary(record)).values()))['beforeProfiles'])
def failure_adjudication(record):
    a=record.get('mocFailureAdjudication')
    require(isinstance(a,dict) and a.get('stage')=='moc-remove-LB-NODE02' and a.get('originalWorkerPid')==7164,'Exact failed MOC attempt7164 must be bound, not forgotten')
    require(a.get('acceptedByParent') is True and a.get('originalRpcFlagsPreserved') is True and a.get('originalProcessAbsent') is True and a.get('noActiveOriginalRpc') is True,'Unclosed/ambiguous MOC attempt blocks03')
    require(a.get('disposition')==MOC_REFUSAL and a.get('parentDecisionSha256')==MOC_RECONCILIATION_SHA and a.get('sourceOrLogEvidenceSha256')==MOC_SOURCE_RECEIPT_SHA,'Exact accepted source-proven pre-offboarding refusal required; raw unknown flags remain')
    for k in ('parentDecisionSha256','originalReceiptSha256','sourceOrLogEvidenceSha256','independentReadbackReceiptSha256'):require(pin(a.get(k)),'Actual no-effect/closure evidence missing: '+k)
    files=a.get('retainedFiles');require(isinstance(files,dict) and files,'Exact retained failure artifacts required')
    require(all('moc-remove-LB-NODE02' in n and all(c.isascii() and (c.isalnum() or c in '._-') for c in n) and pin(s) for n,s in files.items()),'Failure artifact scope/hash differs')
    require(a.get('failedStateFile') in files,'Exact original failure state hash missing')
    return a
def validate_posture(record):
    n=boundary(record);row=next(iter(preview_stages(n).values()));a=record.get('postconditions')
    require(isinstance(a,dict) and pin(a.get('acceptedObserveReceiptSha256')),'Actual accepted handoff observation missing')
    require(a.get('profiles')==row['beforeProfiles'] and a.get('states')==row['beforeStates'],'Actual current guest profile/power differs from exact suffix')
    require(a.get('mocMembers')==row['beforeMocMembers'],'Actual MOC membership does not establish suffix boundary')
    for k in ('allCsvOnlineAccessible','noActiveWorker','noUnadjudicatedRemainingRequestOrWorker','actualCapacityQualified'):require(a.get(k) is True,'Actual handoff qualification missing: '+k)
    require(a.get('poolId')=='{923c0194-3ed4-449a-ae14-0f62861e0ec8}','Exact S2D pool binding differs')
    require(isinstance(a.get('physicalFreeBytes'),int) and a['physicalFreeBytes']>=510*GIB,'Actual S2D repair reserve missing')
    cap=a.get('capacity');require(isinstance(cap,dict) and cap.get('logicalProcessors')==64 and cap.get('physicalCores')==32 and cap.get('memoryBytes',0)>=500*GIB and cap.get('freeMemoryBytes',0)>=32*GIB and cap.get('numaSpanningEnabled') is True,'Actual E64 capacity/reserves missing')
    jobs=a.get('activeStorageJobs');require(isinstance(jobs,list),'Actual job list missing; not assumed empty')
    owners=a.get('deviceOwners');require(isinstance(owners,dict) and len(owners)==24 and all(sum(v==node for v in owners.values())==8 for node in ORDER),'Actual exact24/eight-device ownership missing')
    nodes=a.get('clusterNodes');require(isinstance(nodes,dict) and set(nodes)==set(ORDER),'Actual node posture missing')
    if row['healthProfile']=='strict':
        require(nodes=={x:'Up' for x in ORDER} and a.get('allHealthyAndOk') is True and jobs==[],'Later drain/completion requires full actual convergence')
    else:
        require(nodes['LB-NODE01']==nodes['LB-NODE03']=='Up' and a.get('twoHealthySurvivors') is True and a.get('selectedQualifiedPosture') is True,'Exact selected posture/two healthy survivors required')
        if row['beforeStates']['LB-NODE02']=='Off':require(nodes['LB-NODE02']=='Down','Off selected guest must be Down')
        elif row['effect']=='moc-add':require(nodes['LB-NODE02']=='Up','MOC addition must follow actual resumed Up state')
        elif row['healthProfile']=='selected-maintenance':require(nodes['LB-NODE02']=='Paused' and a.get('selectedEightDevicesActuallyInMaintenance') is True,'Current Paused/eight-device maintenance required')
        else:require(nodes['LB-NODE02'] in ('Paused','Up'),'Qualified compensating return posture missing')
        proof=record.get('retainedOriginalDrainProof');require(isinstance(proof,dict) and pin(proof.get('sha256')) and proof.get('file')=='drain-proof-LB-NODE02.json' and proof.get('planSha256')==ORIGIN_PLAN_SHA and proof.get('sourceCommit')==ORIGIN_COMMIT,'Exact retained02 qualified drain proof required')
        seen=set()
        for job in jobs:
            ids=job.get('affectedVirtualDiskIds',[]);require(len(ids)==1 and ids[0] in KNOWN and job.get('name')==KNOWN[ids[0]] and job.get('poolId')==a['poolId'] and ids[0] not in seen,'Unknown/foreign/duplicate whole-mirror job')
            seen.add(ids[0]);require(job.get('state') in (('Suspended','Running') if row['healthProfile']=='selected-return' or row['effect']=='guest-start' else ('Suspended',)),'Job state outside accepted qv2 posture')
            require(all(x is None or isinstance(x,str) and x in owners for x in job.get('affectedDeviceIds',[])),'Reported repair device outside exact24; null is not attribution')
    stamp=datetime.fromisoformat(a['observedAtUtc'].replace('Z','+00:00'));require(stamp.tzinfo is not None,'Native handoff timestamp/timezone required')
    return True
def validate_handoff(record):
    require(isinstance(record,dict),'Actual accepted settled-prefix handoff missing')
    for k,v in {'schemaVersion':2,'fromOperationId':ORIGIN_ID,'fromPlanSha256':ORIGIN_PLAN_SHA,'fromSourceCommit':ORIGIN_COMMIT,'operationRecordSha256':ORIGIN_OPERATION_SHA,'toOperationId':OPERATION_ID,'toRoot':ROOT}.items():require(record.get(k)==v,'Handoff identity differs: '+k)
    require(record.get('templateOnly') is False and record.get('acceptedByParent') is True and record.get('unfinishedOrAmbiguousPrefix') is False,'Unknown/unaccepted prefix blocks03')
    n=boundary(record);require(record.get('unexecutedSuffix')==list(ALL_KEYS[n:]),'Remainder must be exact original unexecuted suffix')
    failure_adjudication(record)
    require(record.get('qualificationScopeAcceptedByParent') is True and record.get('qualificationFactorySha256')==QV2_FACTORY_SHA,'Accepted qv2 must be explicitly scoped to03')
    evidence=record.get('stageEvidence');require(isinstance(evidence,dict) and set(evidence)==set(ALL_KEYS[:n]),'Every completed original stage requires original evidence')
    for stage,e in evidence.items():
        require(e.get('stage')==e.get('key')==stage and e.get('acceptedByParent') is True and e.get('independentlySettled') is True and e.get('rpcReturned') is True,'Successful original stage is not known/settled: '+stage)
        require(e.get('outcome') in ('rpc-returned-await-independent-observation','rpc-returned-postread-failed-await-independent-observation'),'Unknown RPC cannot be adopted')
        require(e.get('requestFile')=='request-'+stage+'.json' and e.get('stateFile')=='worker-'+stage+'.state.json','Exact original stage paths required')
        require(isinstance(e.get('workerFile'),str) and e['workerFile'].startswith('worker-'+stage+'.') and e['workerFile'].endswith('.ps1') and all(c.isascii() and (c.isalnum() or c in '._-') for c in e['workerFile']),'Actual original worker basename required')
        for k in ('requestSha256','stateSha256','workerSha256','acceptedObserveReceiptSha256'):require(pin(e.get(k)),'Original evidence hash missing: '+stage+'/'+k)
    require(record.get('historicalIntentAdjudicationsRetained') is True,'Original intent flags/history must be preserved')
    return validate_posture(record)
def candidate(handoff=None):
    value=_base_candidate();value['originalOperationReconciliation']=dict(RECONCILIATION);value['predecessorHandoff']=None;value['maintenanceQualification']=None;value['entitlement']=None;value['acceptedPrefixLength']=None;value['transitionContract']['stages']=None
    if handoff is not None:
        validate_handoff(handoff);value['acceptedPrefixLength']=boundary(handoff);value['transitionContract']['stages']=stages(handoff);value['predecessorHandoff']={'record':copy.deepcopy(handoff),'recordSha256':digest(handoff)}
    value['activationRule']='Exact actual contiguous accepted prefix plus source-proven pre-offboarding MOC7164 refusal reconciliation; raw unknown flags retained'
    value['proposedBoundaryNotFreshHandoff']={'prefixLength':1,'remainingStages':24,'firstStage':'moc-remove-LB-NODE02','requiresFreshActualHandoff':True}
    value['knownOriginalMocRefusal']={'parentReconciliationSha256':MOC_RECONCILIATION_SHA,'sourceReadReceiptSha256':MOC_SOURCE_RECEIPT_SHA,'disposition':MOC_REFUSAL,'originalNativeUnknownFlagsPreserved':True,'freshHandoffStillRequired':True}
    value['mocExecutionPeers']=dict(MOC_PEERS)
    return value
def execution_preflight(value,stage,proof,now=None):
    require(value.get('operationId')==OPERATION_ID and value.get('originalOperationReconciliation')==RECONCILIATION,'Exact NEW03 operation/reconciliation required')
    require(value.get('mocExecutionPeers')==MOC_PEERS,'Exact MOC peer policy differs; no fallback')
    h=value.get('predecessorHandoff');require(isinstance(h,dict) and pin(h.get('recordSha256')),'Actual precise handoff missing')
    validate_handoff(h['record']);rows=stages(h['record']);require(value['transitionContract']['stages']==rows and value['acceptedPrefixLength']==boundary(h['record']) and stage in rows,'Only the exact unexecuted suffix is permitted')
    require(digest(h['record'])==h['recordSha256']==proof.get('predecessorHandoffSha256') and proof.get('retained02RootVerified') is True,'Retained02 handoff/proof hash differs')
    q=value.get('maintenanceQualification');require(isinstance(q,dict) and q.get('finalQv2FactorySha256')==QV2_FACTORY_SHA and pin(q.get('qualified03JobsSourceSha256')) and q.get('parent03ScopeDecisionSha256')==h['recordSha256'],'Actual qv2/03 scope binding missing')
    require(proof.get('maintenanceQualificationSha256')==q['qualified03JobsSourceSha256'],'Fresh qv2 proof source differs')
    ent=value.get('entitlement');require(isinstance(ent,dict) and pin(ent.get('receiptSha256')) and proof.get('freshEntitlementVerified') is True and proof.get('entitlementReceiptSha256')==ent['receiptSha256'],'New fresh entitlement/GO required')
    now=now or datetime.now(timezone.utc);at=datetime.fromisoformat(proof['entitlementObservedAtUtc'].replace('Z','+00:00'));until=datetime.fromisoformat(ent['earliestOwnerExpirySast']);expiry=datetime.fromisoformat(value['executionApproval']['expiresAt'])
    require(at.tzinfo is not None and 0<=(now-at).total_seconds()<=300 and until.tzinfo is not None and until>=expiry,'Entitlement stale/shorter than new phase')
    require(proof.get('originalReconciliationSha256')==RECONCILIATION['coordinatorReconciliationSha256'],'Original01 reconciliation binding missing')
    return _base_preflight(value,stage,proof,now)

if __name__=='__main__':print(json.dumps(candidate(),indent=2))
