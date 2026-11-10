"""Exact mixed-profile stages/preflight. Offline source only, not a dispatcher."""
from datetime import datetime, timezone
import hashlib
import json

GIB=1<<30
IDS={'LB-DC01':'f94c71f1-6854-48b9-a9f1-8238c99366d0','LB-NODE01':'3adff629-2f67-449b-ab32-8a8748c46f34','LB-NODE02':'12a44e0c-cc08-4c4c-a812-fa0b56efdbc3','LB-NODE03':'5b6eba15-fa82-4e12-9e45-5ffbcd48c8a9'}
TARGETS={'LB-NODE01':{'cpu':16,'memory':64*GIB},'LB-NODE02':{'cpu':20,'memory':96*GIB},'LB-NODE03':{'cpu':20,'memory':96*GIB}}
ORDER=('LB-NODE02','LB-NODE03','LB-NODE01')
MOC_COMMANDS=('Get-MocNode','Remove-MocPhysicalNode','New-MocPhysicalNode')
INFRA='4c6ca5cc-8c9a-499b-8ffe-c029bbfd3522'


def require(value,message):
    if not value: raise ValueError(message)


def stages():
    profiles={n:{'cpu':2,'memory':4*GIB} if n=='LB-DC01' else {'cpu':8,'memory':64*GIB} for n in IDS}
    states={n:'Running' for n in IDS};result={};members=sorted(ORDER);previous=None
    for node in ORDER:
        effects=['drain','moc-remove','guest-stop','cpu']+(['memory'] if node!='LB-NODE01' else [])+['guest-start','resume','moc-add']
        for effect in effects:
            key=effect+'-'+node
            row={'key':key,'effect':effect,'node':node,'guest':node,'expectedHostLogicalProcessors':64,
                'healthProfile':'strict' if effect=='drain' else ('selected-return' if effect in ('resume','moc-add') else 'selected-maintenance'),
                'beforeProfiles':json.loads(json.dumps(profiles)),'beforeStates':dict(states),
                'targetCpu':TARGETS[node]['cpu'],'targetMemoryBytes':TARGETS[node]['memory'],
                'beforeMocMembers':list(members),'previousStage':previous}
            if effect=='moc-remove':members.remove(node)
            elif effect=='moc-add':members=sorted(members+[node])
            row['afterMocMembers']=list(members)
            result[key]=row
            previous=key
            if effect=='guest-stop':states[node]='Off'
            elif effect=='cpu':profiles[node]['cpu']=TARGETS[node]['cpu']
            elif effect=='memory':profiles[node]['memory']=TARGETS[node]['memory']
            elif effect=='guest-start':states[node]='Running'
    for effect in ('infrastructure-return','complete'):
        result[effect]={'key':effect,'effect':effect,'node':'LB-NODE01','expectedHostLogicalProcessors':64,'healthProfile':'strict',
            'beforeProfiles':json.loads(json.dumps(profiles)),'beforeStates':dict(states),
            'beforeMocMembers':list(members),'afterMocMembers':list(members),'previousStage':previous}
        previous=effect
    return result


def candidate():
    return {'operationId':'smal-foundation-profile-20261109-01','schemaVersion':1,'guestIds':IDS,
        'targetProfiles':TARGETS,'transitionContract':{'version':4,'stages':stages(),'deviceOwners':None},
        'mocContract':None,'maximumExecutionDeadline':'2026-11-10T15:20:00+02:00',
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
    require(plan['maximumExecutionDeadline']=='2026-11-10T15:20:00+02:00' and expiry<=datetime.fromisoformat(plan['maximumExecutionDeadline']),'GO exceeds fixed proposed phase bound')
    require(plan['baseline'] and plan['admission'] and len(plan['transitionContract']['deviceOwners'] or {})==24,'Fresh sealed identities/owners/admission missing')
    require(all(sum(owner==node for owner in plan['transitionContract']['deviceOwners'].values())==8 for node in ORDER),'Exactly eight devices per HCI owner required')
    require(proof['originalOperationsReconciled'] and proof['retainedRootsAbsent'],'Original remote operations/root history unresolved')
    require(proof['exactSourcePublished'] and proof['localWindowsAuthorityVerified'],'Published source or local authority missing')
    require(proof['exactStorageIdentities'] and proof['volumeGrowthBudgetsFit'],'Storage identity/growth reserve missing')
    require(proof['supportedProfilesVerified'],'Setting support not verified')
    moc_contract_preflight(plan['mocContract'])
    require(proof.get('mocContractQualified') is True,'Installed MOC command contract not qualified')
    row=plan['transitionContract']['stages'][stage]
    require(proof.get('mocMembers')==row['beforeMocMembers'],'Actual MOC membership differs from current stage')
    if row['previousStage']:
        require(proof.get('previousStage')==row['previousStage'] and proof.get('previousEffectIndependentlySettled') is True,'Original preceding effect needs independent observation/settlement')
    if row['node']=='LB-NODE01' and row['effect'] in ('drain','guest-stop','infrastructure-return'):
        require(proof.get('infrastructureMigrationAdmitted') is True,'Infrastructure live migration/return not admitted')
    if row['healthProfile']=='strict':require(proof['allHealthyNoJobs'],'Next outage requires healthy converged cluster')
    elif row['healthProfile']=='selected-return':
        require(proof.get('selectedMaintenanceContextVerified') is True and proof['twoHealthySurvivors'],'Selected return-to-service context missing')
    else:require(proof['selectedEightDeviceMaintenanceVerified'] and proof['twoHealthySurvivors'],'Exact planned-maintenance proof missing')
    if row['effect']=='moc-add':require(proof.get('selectedNodeUpObserved') is True,'MOC re-inclusion requires observed Up node')
    require(proof['beforeProfiles']==row['beforeProfiles'] and proof['beforeStates']==row['beforeStates'],'Intermediate VM profile/state differs')
    stamp=datetime.fromisoformat(proof['observedAt']);require(stamp.tzinfo is not None and 0<=(now-stamp).total_seconds()<=300,'Independent observation stale')
    if row['effect']=='guest-start':require(proof['physicalFreeBytes']>=row['targetMemoryBytes']+32*GIB,'Insufficient physical availability for start plus outer reserve')
    require(sum(v['cpu'] for v in row['beforeProfiles'].values())+4<=64,'Outer no-overcommit CPU budget exceeded')
    require(sum(v['memory'] for v in row['beforeProfiles'].values())+32*GIB<=proof['outerMemoryBytes'],'Fixed memory/outer reserve exceeds measured capacity')
    return {'stage':stage,'localEffectPrerequisitesAccepted':True,'transportAuthoritySeparate':True}


def moc_contract_preflight(contract):
    require(isinstance(contract,dict) and set(contract.get('nodes',{}))==set(ORDER),'Exact three-node installed MOC contract missing')
    identity=contract.get('membershipIdentity')
    require(isinstance(identity,dict) and identity.get('semantics')=='WindowsComputerName' and identity.get('location')=='MocLocation','Reviewed actual membership identity semantics/location missing')
    path=identity.get('fieldPath')
    require(isinstance(path,list) and 1<=len(path)<=3 and all(isinstance(p,str) and p for p in path),'Actual observed membership field path missing')
    pin=identity.get('evidenceSha256')
    require(isinstance(pin,str) and len(pin)==64 and all(c in '0123456789abcdef' for c in pin),'Membership shape evidence pin missing')
    initial=contract.get('initialMembership')
    require(isinstance(initial,dict) and membership_names(initial,identity)==sorted(ORDER),'Initial actual three-node MOC membership not observed')
    for node,row in contract['nodes'].items():
        require(row.get('bindingsQualified') is True and row.get('observerNode')==node,'MOC qualifier node identity/bindings differ')
        require(set(row.get('commands',{}))==set(MOC_COMMANDS),'Exact MOC command set missing')
        for name,command in row['commands'].items():
            require(command.get('name')==name and command.get('commandType') in ('Function','Cmdlet'),'Unsupported MOC command binding')
            require(command.get('moduleName') and command.get('moduleVersion') and command.get('modulePath'),'Installed MOC module identity missing')
            require(command['moduleName']=='Moc' and command['moduleVersion']=='1.2.161' and command.get('moduleSha256')=='b9dbda4ab8c0ce6c77d8fa219a153983114afc859f5bb10689f6f3cf71025b7f','Observed Moc 1.2.161 module pin differs')
            require(all(isinstance(command.get(k),str) and len(command[k])==64 and all(c in '0123456789abcdef' for c in command[k]) for k in ('moduleSha256','definitionSha256','contractSha256')),'Installed MOC source/signature hashes missing')
            sets=command.get('parameterSets',[])
            if name=='Get-MocNode':
                valid=[s for s in sets if any(p['name'].casefold()=='location' and p['type']=='System.String' for p in s['parameters']) and any(p['name'].casefold()=='timeoutseconds' and p['type']=='System.Int32' for p in s['parameters']) and all(not p['mandatory'] or p['name'].casefold()=='location' for p in s['parameters'])]
            else:
                valid=[s for s in sets if any(p['name'].casefold()=='nodename' and p['type'] in ('System.String','System.String[]') for p in s['parameters']) and all(not p['mandatory'] or p['name'].casefold()=='nodename' for p in s['parameters'])]
            require(len(valid)==1 or (len(valid)>1 and sum(s.get('isDefault') is True for s in valid)==1),'Observed location/timeout or nodeName MOC signature unsupported or ambiguous: '+name)
    observer=initial.get('observerNode')
    require(observer in ORDER and initial.get('bindingsQualified') is True and initial.get('commands')==contract['nodes'][observer]['commands'],'Initial membership/installed-binding observation does not join')
    return True


def membership_names(observation,identity):
    require(observation.get('membershipDataRead') is True and observation.get('projectionComplete') is True,'Actual bounded membership data missing/unsupported')
    require(observation.get('location')=='MocLocation','Actual membership scope differs')
    names=[]
    for row in observation.get('records',[]):
        fields=[f for f in row.get('fields',[]) if f['path']==identity['fieldPath']]
        require(len(fields)==1,'Reviewed identity field not present exactly once')
        scalar=fields[0]['scalar']
        require(scalar.get('status')=='reported' and scalar.get('type')=='System.String','Membership identity is not a reported native string')
        native=scalar['value']
        matches=[n for n in ORDER if n.casefold()==native.casefold()]
        require(len(matches)==1,'Unknown native identity; no FQDN/GUID mapping permitted')
        names.append(matches[0])
    require(len(names)==len(set(names)),'Duplicate actual membership identity')
    return sorted(names)


if __name__=='__main__':print(json.dumps(candidate(),indent=2))
