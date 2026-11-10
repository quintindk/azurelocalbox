"""Exact mixed-profile stages/preflight. Offline source only, not a dispatcher."""
from datetime import datetime, timezone
import hashlib
import json

GIB=1<<30
IDS={'LB-DC01':'f94c71f1-6854-48b9-a9f1-8238c99366d0','LB-NODE01':'3adff629-2f67-449b-ab32-8a8748c46f34','LB-NODE02':'12a44e0c-cc08-4c4c-a812-fa0b56efdbc3','LB-NODE03':'5b6eba15-fa82-4e12-9e45-5ffbcd48c8a9'}
TARGETS={'LB-NODE01':{'cpu':16,'memory':64*GIB},'LB-NODE02':{'cpu':20,'memory':96*GIB},'LB-NODE03':{'cpu':20,'memory':96*GIB}}
ORDER=('LB-NODE02','LB-NODE03','LB-NODE01')
INFRA='4c6ca5cc-8c9a-499b-8ffe-c029bbfd3522'


def require(value,message):
    if not value: raise ValueError(message)


def stages():
    profiles={n:{'cpu':2,'memory':4*GIB} if n=='LB-DC01' else {'cpu':8,'memory':64*GIB} for n in IDS}
    states={n:'Running' for n in IDS};result={}
    for node in ORDER:
        effects=['drain','guest-stop','cpu']+(['memory'] if node!='LB-NODE01' else [])+['guest-start','resume']
        for effect in effects:
            key=effect+'-'+node
            row={'key':key,'effect':effect,'node':node,'guest':node,'expectedHostLogicalProcessors':64,
                'healthProfile':'strict' if effect=='drain' else 'selected-maintenance',
                'beforeProfiles':json.loads(json.dumps(profiles)),'beforeStates':dict(states),
                'targetCpu':TARGETS[node]['cpu'],'targetMemoryBytes':TARGETS[node]['memory']}
            result[key]=row
            if effect=='guest-stop':states[node]='Off'
            elif effect=='cpu':profiles[node]['cpu']=TARGETS[node]['cpu']
            elif effect=='memory':profiles[node]['memory']=TARGETS[node]['memory']
            elif effect=='guest-start':states[node]='Running'
    for effect in ('infrastructure-return','complete'):
        result[effect]={'key':effect,'effect':effect,'node':'LB-NODE01','expectedHostLogicalProcessors':64,'healthProfile':'strict',
            'beforeProfiles':json.loads(json.dumps(profiles)),'beforeStates':dict(states)}
    return result


def candidate():
    return {'operationId':'smal-foundation-profile-20261109-01','schemaVersion':1,'guestIds':IDS,
        'targetProfiles':TARGETS,'transitionContract':{'version':3,'stages':stages(),'deviceOwners':None},
        'baseline':None,'admission':None,'executionApproval':{'parentGo':False,'expiresAt':None},
        'retainedRootsMustBeAbsentOrSeparatelyReconciled':True,
        'profileSupportBasis':'measured Gen2/version12, nested=true, max32 processors/vNUMA, fixed RAM, maximum1TiB; official Hyper-V 2025 Gen2 limits exceed targets',
        'nativeEffectsApproved':False}


def setting_preflight(node,observed):
    require(node in TARGETS,'Exact selected HCI node required')
    require(observed['id']==IDS[node],'VM identity differs')
    require(observed['generation']==2 and observed['version']=='12.0','Measured VM generation/version differs')
    require(observed['nested'] is True and observed['dynamicMemory'] is False,'Nested/fixed profile differs')
    target=TARGETS[node]
    require(observed['maxCpuPerNuma']>=target['cpu'],'Target exceeds configured vNUMA processor ceiling')
    require(observed['minimumMemoryBytes']<=target['memory']<=observed['maximumMemoryBytes'],'Target exceeds configured fixed-memory bounds')
    require(observed['outerNumaSpanning'] is True,'Unexpected NUMA-spanning change')
    return {'settingsSupportedByObservedBounds':True,'cimFormattingIsSupportGate':False,'executionAdmitted':False}


def execution_preflight(plan,stage,proof,now=None):
    now=now or datetime.now(timezone.utc)
    require(stage in plan['transitionContract']['stages'],'Unknown effect stage')
    require(plan['executionApproval']['parentGo'] is True,'No execution GO')
    expiry=datetime.fromisoformat(plan['executionApproval']['expiresAt']);require(expiry.tzinfo is not None and now<expiry,'Expired/malformed execution GO')
    require(plan['baseline'] and plan['admission'] and len(plan['transitionContract']['deviceOwners'] or {})==24,'Fresh sealed identities/owners/admission missing')
    require(all(sum(owner==node for owner in plan['transitionContract']['deviceOwners'].values())==8 for node in ORDER),'Exactly eight devices per HCI owner required')
    require(proof['originalOperationsReconciled'] and proof['retainedRootsAbsent'],'Original remote operations/root history unresolved')
    require(proof['exactSourcePublished'] and proof['localWindowsAuthorityVerified'],'Published source or local authority missing')
    require(proof['exactStorageIdentities'] and proof['volumeGrowthBudgetsFit'],'Storage identity/growth reserve missing')
    require(proof['supportedProfilesVerified'],'Setting support not verified')
    row=plan['transitionContract']['stages'][stage]
    if row['node']=='LB-NODE01' and row['effect'] in ('drain','guest-stop','infrastructure-return'):
        require(proof.get('infrastructureMigrationAdmitted') is True,'Infrastructure live migration/return not admitted')
    if row['healthProfile']=='strict':require(proof['allHealthyNoJobs'],'Next outage requires healthy converged cluster')
    else:require(proof['selectedEightDeviceMaintenanceVerified'] and proof['twoHealthySurvivors'],'Exact planned-maintenance proof missing')
    require(proof['beforeProfiles']==row['beforeProfiles'] and proof['beforeStates']==row['beforeStates'],'Intermediate VM profile/state differs')
    stamp=datetime.fromisoformat(proof['observedAt']);require(stamp.tzinfo is not None and 0<=(now-stamp).total_seconds()<=300,'Independent observation stale')
    if row['effect']=='guest-start':require(proof['physicalFreeBytes']>=row['targetMemoryBytes']+32*GIB,'Insufficient physical availability for start plus outer reserve')
    require(sum(v['cpu'] for v in row['beforeProfiles'].values())+4<=64,'Outer no-overcommit CPU budget exceeded')
    require(sum(v['memory'] for v in row['beforeProfiles'].values())+32*GIB<=proof['outerMemoryBytes'],'Fixed memory/outer reserve exceeds measured capacity')
    return {'stage':stage,'localEffectPrerequisitesAccepted':True,'transportAuthoritySeparate':True}


if __name__=='__main__':print(json.dumps(candidate(),indent=2))
