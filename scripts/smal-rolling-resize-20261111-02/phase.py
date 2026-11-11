"""11 November two-node continuation. Source generation is offline; no old GO renewal."""
import base64
import copy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import subprocess
import urllib.parse
from types import FunctionType,SimpleNamespace

HERE=Path(__file__).resolve().parent
OLD=Path('/tmp/opencode/smal-rolling03-future-aliases-20261110')
OLD_CONTRACT='1ab59c1abbc77ecc61f09c76ddf99ced09673e09802e36bcef206ac22489bcf5'
ROOT=Path('/home/quintin/play/azurelocalbox')
OP='smal-foundation-profile-20261111-02'
NATIVE_ROOT=r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261111-02'
DEADLINE='2026-11-11T15:20:00+02:00'
INITIAL_API=Path('/tmp/opencode/smal-resumption-20261111/access-initial.json')
INITIAL_API_SHA='932a159871da61bd3d7ad7eca2b052d128b221523bc70878cc096138d69a7298'
sha=lambda b:hashlib.sha256(b).hexdigest()
canonical=lambda v:json.dumps(v,sort_keys=True,separators=(',',':')).encode()

def require(ok,message):
    if not ok:raise ValueError(message)

def load_old():
    names=('correction.py','identity_adapter.ps1','capture.ps1.in','serial03.py','off-maintenance-policy.json','protection.py','protection.ps1')
    require(sha(canonical({n:sha((OLD/n).read_bytes()) for n in names}))==OLD_CONTRACT,'Reviewed V4 source changed')
    spec=importlib.util.spec_from_file_location('_reviewed_v4_correction',OLD/'correction.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

v4=load_old()

def original():return v4.original_plan()

def stages():
    old=original();keys=v4.original_order(old)
    keys=keys[keys.index('drain-LB-NODE03'):]
    result={k:copy.deepcopy(old['transitionContract']['stages'][k]) for k in keys}
    previous=None
    for key,row in result.items():
        require(row.get('node')!='LB-NODE02' and not (row['effect']=='memory' and row['node']=='LB-NODE01'),'NODE02 replay/NODE01 RAM write forbidden')
        row['previousStage']=previous;previous=key
    return result

def context():
    old=original()
    return {'operationId':OP,'root':NATIVE_ROOT,'maximumExecutionDeadline':DEADLINE,
            'guestIds':old['guestIds'],'baseline':old['baseline'],'admission':old['admission'],
            'mocContract':old['mocContract'],'mocExecutionPeers':{'LB-NODE03':'LB-NODE01','LB-NODE01':'LB-NODE02'},
            'transitionContract':{'deviceOwners':old['transitionContract']['deviceOwners'],'stages':stages()},
            'targetProfiles':old['targetProfiles'],'nativeEffectsApproved':False,
            'referenceOnlyOld03PlanSha256':v4.PLAN_SHA,'referenceOnlyOld03SourceCommit':v4.ANCHOR,
            'old03GoNotRenewed':True,'old04GoNotRenewed':True,'postNightlyProtectionProjection':None,
            'executionApproval':{'parentGo':False,'expiresAt':None}}

def read_functions():
    # Pure existing read definitions, no old dispatcher, old GO or protection760c decision.
    spec=importlib.util.spec_from_file_location('_current_original_build',v4.BUILD_PATH)
    previous=sys.modules.get('plan')
    p_spec=importlib.util.spec_from_file_location('_original_profile_plan',v4.BUILD_PATH.parent/'plan.py')
    p=importlib.util.module_from_spec(p_spec);p_spec.loader.exec_module(p);sys.modules['plan']=p
    try:
        b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b);text=b.render()['common.ps1']
    finally:
        if previous is None:sys.modules.pop('plan',None)
        else:sys.modules['plan']=previous
    # Exactly one three-node inventory per independent read; unused nested ARP/DNS inventory omitted.
    begin=text.index('function Read-ComputeSnapshot(');end=text.index('\nfunction Read-ComputeDcNetwork',begin)
    fn=text[begin:end];a=fn.rfind('\n',0,fn.index('network = @{'))+1;b=fn.rfind('\n',0,fn.index('nestedVms = @(',a))+1
    fn=fn[:a]+fn[b:]
    text=text[:begin]+fn+text[end:]
    text=text.replace(r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-03',NATIVE_ROOT)
    return text

def capture_source(node='LB-NODE03'):
    require(node in ('LB-NODE03','LB-NODE01'),'Only selected two-node captures')
    prefix="$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n$entry=[pscustomobject]@{node='"+node+"'}\n"
    prefix+="$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(canonical(context())).decode()+"'))|ConvertFrom-Json)\n"
    tail=(HERE/'capture.ps1.in').read_text()
    if node=='LB-NODE01':
        tail=tail.replace("'LB-NODE03'=@{cpu=8;memory=64GB}","'LB-NODE03'=@{cpu=20;memory=96GB}")
        tail=tail.replace("Read-ProfileMoc 'LB-NODE01'","Read-ProfileMoc 'LB-NODE02'")
        tail=tail.replace("$moc.observerNode -ceq 'LB-NODE01'","$moc.observerNode -ceq 'LB-NODE02'")
        tail=tail.replace("$plan.mocContract.nodes.'LB-NODE01'.commands","$plan.mocContract.nodes.'LB-NODE02'.commands")
    return prefix+read_functions()+'\n'+tail

def contract():
    return sha(canonical({n:sha((HERE/n).read_bytes()) for n in ('phase.py','capture.ps1.in','runtime.ps1','observe.ps1.in','convergence.ps1.in')}))

def policy_sha():
    return sha(canonical({'operationId':OP,'deadline':DEADLINE,'selectedNodes':['LB-NODE03','LB-NODE01'],
                          'effects':['cpu','memory','guest-start'],'basis':'actual original drain + fresh current pre-Stop read + returned Stop + exact current24 ObjectId join; no current native flag rewrite'}))

def entitlement(path,pin,now):
    raw=Path(path).read_bytes();require(sha(raw)==pin,'Actual new API SHA differs')
    initial_raw=INITIAL_API.read_bytes();require(sha(initial_raw)==INITIAL_API_SHA,'Initial new-day Owner scope reference changed')
    initial=json.loads(initial_raw);actual=json.loads(raw)
    at=datetime.fromisoformat(actual['observedAtSast']);cut=datetime.fromisoformat(DEADLINE)
    require(at.tzinfo is not None and 0<=(now-at).total_seconds()<=300 and actual.get('activeOwnerVerified') is True
            and actual['principalId']==initial['principalId'] and actual['tenantId']==initial['tenantId'] and actual['resourceMutations']==0,'Fresh current effective-Owner identity required; never restamp')
    ends=[]
    for name,b in initial['scopes'].items():
        x=actual['scopes'][name];a=x['assignment'];old=b['assignment']
        require(x['complete'] is True and a['principalId']==actual['principalId'] and a['scope']==old['scope']
                and a['roleDefinitionId']==old['roleDefinitionId'] and a['assignmentType']=='Activated' and a['status']=='Provisioned'
                and datetime.fromisoformat(a['startDateTime'].replace('Z','+00:00'))<=at<=now<datetime.fromisoformat(a['endDateTime'].replace('Z','+00:00'))
                and datetime.fromisoformat(a['endDateTime'].replace('Z','+00:00'))>=cut,'Current effective Owner does not cover exact new-day cutoff')
        ends.append(datetime.fromisoformat(a['endDateTime'].replace('Z','+00:00')))
    return {'currentEffectiveOwnerVerified':True,'actualReceiptSha256':pin,'sourceFile':str(path),'observedAtUtc':at.isoformat(),'earliestOwnerExpiry':min(ends).isoformat(),'initialNewDayScopeReferenceSha256':INITIAL_API_SHA}

def refresh_owner(output_path):
    """Actual GET-only current CLI identity/PIM read. No activation/account switch/token export."""
    raw=INITIAL_API.read_bytes();require(sha(raw)==INITIAL_API_SHA,'New-day initial scope reference changed');initial=json.loads(raw)
    def az_json(args):
        return json.loads(subprocess.run(['az',*args,'--only-show-errors','-o','json'],check=True,capture_output=True,text=True).stdout)
    token=az_json(['account','get-access-token','--resource','https://management.azure.com/'])
    payload=token['accessToken'].split('.')[1];claims=json.loads(base64.urlsafe_b64decode(payload+'='*((4-len(payload)%4)%4)))
    require(claims.get('oid')==initial['principalId'] and claims.get('tid')==initial['tenantId'],'Current authenticated ARM principal/tenant changed; no credential fallback')
    del token,payload,claims
    scopes={};clock=datetime.now(timezone.utc);cut=datetime.fromisoformat(DEADLINE)
    for name,b in initial['scopes'].items():
        scope=b['assignment']['scope'];filter_value="principalId eq '"+initial['principalId']+"'"
        url='https://management.azure.com'+scope+'/providers/Microsoft.Authorization/roleAssignmentScheduleInstances?api-version=2020-10-01&$filter='+urllib.parse.quote(filter_value)
        matches=[];pages=0
        while url:
            parsed=urllib.parse.urlparse(url);require(parsed.scheme=='https' and parsed.hostname=='management.azure.com' and parsed.path.lower()==(scope+'/providers/Microsoft.Authorization/roleAssignmentScheduleInstances').lower(),'Unexpected ARM pagination destination')
            response=az_json(['rest','--method','get','--url',url]);pages+=1;require(pages<=32,'Bounded effective-Owner traversal exceeded')
            for item in response.get('value',[]):
                a=item.get('properties',{})
                if (a.get('principalId')==initial['principalId'] and a.get('scope')==scope and a.get('roleDefinitionId')==b['assignment']['roleDefinitionId']
                    and a.get('assignmentType')=='Activated' and a.get('status')=='Provisioned'
                    and datetime.fromisoformat(a['startDateTime'].replace('Z','+00:00'))<=clock<datetime.fromisoformat(a['endDateTime'].replace('Z','+00:00'))
                    and datetime.fromisoformat(a['endDateTime'].replace('Z','+00:00'))>=cut):matches.append(a)
            url=response.get('nextLink')
        require(len(matches)==1,'Current exact active Owner missing/ambiguous/short at '+name)
        scopes[name]={'complete':True,'subscriptionId':b['subscriptionId'],'activeOwnerCount':1,'assignment':matches[0],'apiPages':pages}
    record={'activeOwnerVerified':True,'observedAtSast':datetime.now().astimezone().isoformat(),'principalId':initial['principalId'],
            'tenantId':initial['tenantId'],'resourceMutations':0,'scopes':scopes}
    path=Path(output_path);data=canonical(record)
    with path.open('xb') as f:f.write(data)
    pin=sha(data);return path,pin,entitlement(path,pin,datetime.now(timezone.utc))

def seal_phase(value,approval,handoff,source_commit):
    require(approval.get('acceptedByParent') is True and approval.get('operationId')==OP
            and approval.get('reviewedSourceSha256')==contract() and approval.get('selectedStages')==list(stages())
            and approval.get('expiresAt')==DEADLINE,'Exact parent-reviewed new-day selected-profile approval required')
    require(handoff.get('acceptedByParent') is True and handoff.get('previousWriterExited') is True and handoff.get('moc3Observed') is True,
            'Actual hardware writer lane transfer required')
    require(re.fullmatch('[a-f0-9]{40}',source_commit) and source_commit!=v4.ANCHOR,'Actual NEW published factory commit required, never old03 anchor')
    require(value['postNightlyProtectionProjection']['acceptedByParent'] is True,'Actual current security projection remains unbound')
    sealed=copy.deepcopy(value);sealed.update(sourceReviewed=True,reviewedSourceSha256=contract(),sourceCommit=source_commit,
        writerLaneHandoff=copy.deepcopy(handoff),nativeEffectsApproved=True,executionApproval={'parentGo':True,'expiresAt':DEADLINE})
    return sealed

def phase_digest(value):return sha(canonical(value))

def alias_source(value):
    source=(OLD/'identity_adapter.ps1').read_text()
    changes={v4.PLAN_SHA:phase_digest(value),v4.ANCHOR:value['sourceCommit'],
             'smal-foundation-profile-20261110-03':OP,'2026-11-10T23:30:00+02:00':DEADLINE,
             r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-03':NATIVE_ROOT,
             'dffa8bf0db38e770d3fb1156153cd9b07c45fc5104095db0b67cf7802c60c674':policy_sha(),
             '.journal-fixed-01.ps1':'.scriptblock.ps1','restartStabilityReceiptSha256':'healthyPreOffIdentityReceiptSha256'}
    for before,after in changes.items():source=source.replace(before,after)
    return source

def map_binding(value,read_receipt_path,read_pin,selected_node,accepted_at):
    raw=Path(read_receipt_path).read_bytes();require(sha(raw)==read_pin,'Exact accepted genuine identity read differs')
    receipt=json.loads(raw);o=receipt['result'];s=o['snapshot'];identity=o['identity']
    require(o['operationId']==OP and o['mutationPerformed'] is False and receipt['status']=='complete' and receipt['sshExitCode']==0
            and receipt.get('strictPinnedHostKey') is True and receipt.get('loopbackOnly') is True and receipt.get('passwordAuthentication') is False
            and receipt.get('renderedSourceSha256')==sha(capture_source(selected_node).encode()),'Actual exact published new-phase capture/transport required')
    at=datetime.fromisoformat(identity['observedAtUtc'].replace('Z','+00:00'));accepted=datetime.fromisoformat(accepted_at)
    require(0<=(accepted-at).total_seconds()<=300,'Actual map must be fresh when accepted')
    require(identity['poolId']==value['baseline']['clusterStatic']['poolId'] and len(identity['members'])==24
            and len({m['objectId'] for m in identity['members']})==24
            and {m['uniqueId']:m['size'] for m in identity['members']}=={m['id']:m['size'] for m in value['baseline']['clusterStatic']['members']},'Actual opaque all24 ObjectId/VPD/size bijection required')
    by_object={m['objectId']:m for m in identity['members']};links=identity['ownerLinks']
    require(len(links)==24 and len({l['objectId'] for l in links})==24
            and all(l['objectId'] in by_object and l['uniqueId']==by_object[l['objectId']]['uniqueId']
                    and l['owner']==by_object[l['objectId']]['owner']==value['transitionContract']['deviceOwners'][l['uniqueId']] for l in links),
            'Actual exact24 physically-connected ObjectId/VPD/owner links required')
    mapping={'schemaVersion':2,'status':'healthy-pre-off-object-identity','mutationPerformed':False,'planSha256':phase_digest(value),
             'sourceAnchor':value['sourceCommit'],'captureBeganAtUtc':o['captureBeganAtUtc'],'atUtc':identity['observedAtUtc'],
             'poolId':identity['poolId'],'members':identity['members'],'ownerLinks':identity['ownerLinks'],'outerGuestsStatic':s['guestsStatic'],
             'allThreeUpHealthy':True,'activeStorageJobCount':0,'mapAccepted':False}
    decision={'accepted':True,'selectedNode':selected_node,'planSha256':phase_digest(value),'transportReceiptSha256':read_pin,
              'healthyPreOffIdentityReceiptSha256':read_pin,'acceptedAtUtc':accepted_at,'expiresAtUtc':DEADLINE,
              'identityMapValidThroughSingleOriginalOutage':True,'offConfigurationHistoricalMaintenancePolicySha256':policy_sha(),
              'drainStageKey':'drain-'+selected_node,'stopStageKey':'guest-stop-'+selected_node}
    return {'map':mapping,'acceptance':decision,'provenance':{'transportReceiptSha256':read_pin,'transportReceiptPath':str(read_receipt_path),
            'sourceValuePath':'result.identity + result.snapshot.guestsStatic','derivedPayloadCanonicalSha256':sha(canonical(mapping)),
            'derivedPayloadIsNativeBytes':False},'identityBindingSha256':sha(canonical(decision))}

def runtime_functions(value,proof):
    """Use V4's exact ObjectId source splice, changing only the new phase binding."""
    alias=alias_source(value);binding=proof['identityBinding']
    def decode(name,obj):
        return "$"+name+"=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(canonical(obj)).decode()+"'))|ConvertFrom-Json)\n"
    def new_binding(*args):
        return alias+'\n'+decode('futureMap',binding['map'])+decode('futureAcceptance',binding['acceptance'])+decode('futureMapProvenance',binding['provenance'])+decode('futureContinuity',proof.get('continuity',{}))+"$futureIdentityBindingSha256='"+binding['identityBindingSha256']+"'\n"
    # Original render is read-only. V4 splices are reused, never old capsule approval.
    spec=importlib.util.spec_from_file_location('_day_profile_build',v4.BUILD_PATH)
    p_spec=importlib.util.spec_from_file_location('_day_profile_reference',v4.BUILD_PATH.parent/'plan.py')
    p=importlib.util.module_from_spec(p_spec);p_spec.loader.exec_module(p);previous=sys.modules.get('plan');sys.modules['plan']=p
    try:b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b);files=b.render()
    finally:
        if previous is None:sys.modules.pop('plan',None)
        else:sys.modules['plan']=previous
    namespace=dict(v4.adapt_sources.__globals__);namespace.update(binding_source=new_binding,factory_contract=contract)
    # Skip only V4's unrelated worker edits: execute the reviewed common source
    # splice up to its completed common boundary, using the exact reviewed code.
    import inspect
    source=inspect.getsource(v4.adapt_sources);cut=source.index("    stop = '                Stop-VM")
    source=source[:cut]+"    return {'common.ps1':common}\n"
    exec(compile(source,'<reviewed-V4-common-splice-new-phase-binding>','exec'),namespace)
    common=namespace['adapt_sources'](files,None,binding['acceptance'],binding['acceptance']['selectedNode'],proof.get('continuity',{}))['common.ps1']
    old64=base64.b64encode((OLD/'identity_adapter.ps1').read_bytes()).decode();new64=base64.b64encode(alias.encode()).decode()
    require(common.count(old64)==1,'Exact remote alias source boundary differs');common=common.replace(old64,new64)
    common=common.replace(r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-03',NATIVE_ROOT)
    before='            Assert-FutureOutageContinuity $futureAcceptance $plan $stage $futureContinuity $futureIdentityBindingSha256'
    require(common.count(before)==1,'Exact snapshot continuity boundary differs')
    common=common.replace(before,"            if($entry.effect -cnotin @('infrastructure-return','complete')){Assert-FutureOutageContinuity $futureAcceptance $plan $stage $futureContinuity $futureIdentityBindingSha256}",1)
    # Reuse the compact canonical reader, without duplicate nested network inventory.
    start=common.index('function Read-ComputeSnapshot(');end=common.index('\nfunction Read-ComputeDcNetwork',start);fn=common[start:end]
    a=fn.rfind('\n',0,fn.index('network = @{'))+1;z=fn.rfind('\n',0,fn.index('nestedVms = @(',a))+1;fn=fn[:a]+fn[z:]
    return common[:start]+fn+common[end:]+'\n'+(HERE/'runtime.ps1').read_text()

def effect_source(value,stage,proof):
    require(value['operationId']==OP and value['root']==NATIVE_ROOT and value['maximumExecutionDeadline']==DEADLINE
            and value['sourceReviewed'] is True and value['reviewedSourceSha256']==contract()
            and value['sourceCommit']!=v4.ANCHOR and re.fullmatch('[a-f0-9]{40}',value['sourceCommit'])
            and value['executionApproval']['parentGo'] is True and value['nativeEffectsApproved'] is True,'Explicit reviewed new-day phase GO/source required; old GO cannot be extended')
    require(stage in stages() and value['transitionContract']['stages']==stages(),'Exact two-node original profile sequence required')
    require(value['postNightlyProtectionProjection']['acceptedByParent'] is True and value['writerLaneHandoff']['acceptedByParent'] is True,'Current accepted security projection/lane transfer remain unbound')
    actual_entitlement=entitlement(proof['entitlement']['sourceFile'],proof['entitlement']['actualReceiptSha256'],datetime.now(timezone.utc))
    require(actual_entitlement==proof['entitlement'],'Exact fresh actual API provenance differs before effect source generation')
    if proof.get('pendingProtectionTransitions'):
        require(proof.get('acceptedCurrentProtectionProjection',{}).get('acceptedByParent') is True,'Actual post-start opaque protection changes still require explicit parent qualification before this effect')
    digest=phase_digest(value)
    def decode(name,obj):return "$"+name+"=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(canonical(obj)).decode()+"'))|ConvertFrom-Json)\n"
    prefix="param([string]$executingSourceSha256)\n$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n"+decode('plan',value)+decode('proof',proof)
    prefix+="$planSha='"+digest+"'\n$sourceCommit='"+value['sourceCommit']+"'\n$factoryContractSha256='"+contract()+"'\n$stage='"+stage+"'\n$effectKey=$stage\n$entry=$plan.transitionContract.stages.PSObject.Properties[$stage].Value\n$root=$plan.root\n$statePath=Join-Path $root ('worker-'+$stage+'.state.json')\n"
    body=prefix+runtime_functions(value,proof)+"\nInvoke-DayEffect|ConvertTo-Json -Depth 60 -Compress\n"
    block_sha=sha(body.encode())
    loader="$ErrorActionPreference='Stop'\n$body=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(body.encode()).decode()+"'))\n$block=[ScriptBlock]::Create($body)\n$hash=[Security.Cryptography.SHA256]::Create();try{$actual=[BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($block.ToString()))).Replace('-','').ToLowerInvariant()}finally{$hash.Dispose()}\nif($actual -cne '"+block_sha+"'){throw 'Actual ScriptBlock self hash differs before execution'}\n"
    # Persist the exact body in the protected new root before synchronous invocation.
    # Native runtime creates the root/ACL; its first intent writes the same body.
    loader+="$global:DayExecutingScriptBlockText=$body\n& $block $actual\n"
    return {'script':loader,'workerScriptBlock':body,'workerScriptBlockSha256':block_sha,'transportSourceSha256':sha(loader.encode()),'planSha256':digest,'stage':stage,'nativeExecuted':False}

def begin_outage(value,identity_binding,entitlement_proof,previous_observation=None):
    require(identity_binding['acceptance']['selectedNode'] in ('LB-NODE03','LB-NODE01'),'Exact next selected node required')
    proof={'identityBinding':identity_binding,'entitlement':entitlement_proof,'continuity':{},'continuityReceipts':{},'drainProof':None,
           'acceptedPreviousObserveReceiptSha256':None,'acceptedPreviousWorkerScriptBlockSha256':None,
           'validatedAtUtc':entitlement_proof['observedAtUtc'],'acceptedCurrentProtectionProjection':None}
    if previous_observation:
        proof.update(acceptedPreviousObserveReceiptSha256=previous_observation['acceptedPreviousObserveReceiptSha256'],
                     acceptedPreviousWorkerScriptBlockSha256=previous_observation['acceptedPreviousWorkerScriptBlockSha256'],
                     acceptedCurrentProtectionProjection=previous_observation.get('acceptedCurrentProtectionProjection'),
                     continuityReceipts=copy.deepcopy(previous_observation.get('continuityReceipts',{})))
    return proof

def observer_source(value,stage,proof,expected_worker_sha):
    def decode(name,obj):return "$"+name+"=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(canonical(obj)).decode()+"'))|ConvertFrom-Json)\n"
    prefix="$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n"+decode('plan',value)+decode('proof',proof)
    prefix+="$planSha='"+phase_digest(value)+"'\n$sourceCommit='"+value['sourceCommit']+"'\n$stage='"+stage+"'\n$entry=$plan.transitionContract.stages.PSObject.Properties[$stage].Value\n$root=$plan.root\n$expectedWorkerSha='"+expected_worker_sha+"'\n"
    return prefix+runtime_functions(value,proof)+'\n'+(HERE/'observe.ps1.in').read_text()

def convergence_source():
    # No nested/full inventory and no action. Used only if the independent return
    # observation reports unfinished storage convergence before the next outage.
    prefix="$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(canonical(context())).decode()+"'))|ConvertFrom-Json)\n"
    return prefix+v4.read_helpers()+'\n'+(HERE/'convergence.ps1.in').read_text()

def packet(value,stage,proof,output):
    effect=effect_source(value,stage,proof);observe=observer_source(value,stage,proof,effect['workerScriptBlockSha256'])
    blobs={stage+'.execute.ps1':effect['script'].encode(),stage+'.observe.ps1':observe.encode(),
           'stage-input-'+stage+'.json':canonical({'plan':value,'proof':proof})}
    root=Path(output);require(root.resolve().is_relative_to(HERE.resolve()),'Only this private new-day execution workspace may receive generated files')
    require(not any((root/name).exists() for name in blobs),'Original stage source exists; inspect, never overwrite/rekey')
    root.mkdir(parents=True,exist_ok=True)
    manifest={'operationId':OP,'stage':stage,'planSha256':effect['planSha256'],'factoryContractSha256':contract(),
              'factorySourceCommit':value['sourceCommit'],'workerScriptBlockSha256':effect['workerScriptBlockSha256'],
              'observerSourceSha256':sha(observe.encode()),'executeSourceSha256':effect['transportSourceSha256'],
              'nativeExecuted':False,'artifacts':{name:{'path':str(root/name),'sha256':sha(data)} for name,data in blobs.items()}}
    for name,data in blobs.items():
        with (root/name).open('xb') as f:f.write(data)
    with (root/('manifest-'+stage+'.json')).open('xb') as f:f.write(canonical(manifest))
    return manifest

def execute_packet(manifest,execute_receipt_name,observe_receipt_name):
    """Explicit lane-owner invocation only, after parent publication. No retry/rekey/Git."""
    require(manifest['operationId']==OP and manifest['factoryContractSha256']==contract()
            and manifest['stage'] in stages(),'Exact reviewed current phase/stage packet required')
    stage=manifest['stage'];prefix='scripts/rolling-profile-live-20261111-02/'
    for suffix in ('execute.ps1','observe.ps1'):
        name=stage+'.'+suffix;require(sha((ROOT/prefix/name).read_bytes())==manifest['artifacts'][name]['sha256'],'Parent publication does not match exact new source: '+name)
    def invoke(suffix,name):
        path=ROOT/'docs/deployment-2026-10-27'/('private-ssh-'+name+'.json')
        require(not path.exists(),'Original receipt exists; inspect, never replay/rekey')
        subprocess.run(['python3','-B',str(ROOT/'scripts/smal-private-powershell.py'),'--script',prefix+stage+'.'+suffix+'.ps1','--receipt',name],cwd=ROOT,check=True)
        return path,json.loads(path.read_bytes())
    execute_path,actual=invoke('execute',execute_receipt_name);o=actual.get('result',{});w=o.get('worker',{})
    require(actual.get('status')=='complete' and actual.get('sshExitCode')==0
            and actual.get('renderedSourceSha256')==manifest['executeSourceSha256'] and actual.get('commit')!=v4.ANCHOR
            and o.get('planSha256')==manifest['planSha256'] and o.get('stage')==stage
            and o.get('workerScriptBlockSha256')==manifest['workerScriptBlockSha256']
            and w.get('rpcReturned') is True and w.get('phase')=='returned','Synchronous effect unknown/failed/incomplete. STOP; no replay or automatic compensation')
    observe_path,observed=invoke('observe',observe_receipt_name)
    require(observed.get('status')=='complete' and observed.get('sshExitCode')==0
            and observed.get('renderedSourceSha256')==manifest['observerSourceSha256'],'Independent after-read failed. Effect is not independently settled; STOP')
    return {'executeReceiptPath':str(execute_path),'executeReceiptSha256':sha(execute_path.read_bytes()),
            'observeReceiptPath':str(observe_path),'observeReceiptSha256':sha(observe_path.read_bytes()),
            'stage':stage,'actualEffectReturned':True,'independentAfterReadPerformed':True}

def reviewed_guards():
    # Pure V4 scalar/lineage checks. Never call its expired compiler or controller.
    previous=sys.modules.get('correction');sys.modules['correction']=v4
    spec=importlib.util.spec_from_file_location('_reviewed_day_lineage',OLD/'serial03.py')
    try:m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    finally:
        if previous is None:sys.modules.pop('correction',None)
        else:sys.modules['correction']=previous
    return m

def check_snapshot(value,snapshot,row,proof,receipt):
    import inspect
    guards=reviewed_guards();q=guards.q;digest=phase_digest(value);binding=proof['identityBinding']
    require(snapshot['mutationPerformed'] is False,'Actual read is not GET-only')
    for k in ('hostStatic','volumesStatic','clusterStatic'):require(snapshot[k]==value['baseline'][k],'Actual accepted new-phase static drift: '+k)
    require(len(snapshot['guestsStatic'])==4 and snapshot['states']==row['beforeStates'],'Actual current original four VM states differ')
    pending=[]
    for g in snapshot['guestsStatic']:
        old=next(x for x in value['baseline']['guestsStatic'] if x['name']==g['name'])
        require({k:x for k,x in g.items() if k not in ('cpu','memory','protectorHash')}=={k:x for k,x in old.items() if k not in ('cpu','memory','protectorHash')},'Actual VHD/NIC/TPM/SecureBoot/non-profile field changed')
        require({'cpu':g['cpu'],'memory':g['memory']}==row['beforeProfiles'][g['name']],'Actual selected profile differs from exact next original key')
        if g['protectorHash']!=old['protectorHash']:pending.append({'node':g['name'],'baselineRawProtectorHash':old['protectorHash'],'currentRawProtectorHash':g['protectorHash'],'mechanismClaimed':False})
    cap=snapshot['hostCapacity'];require(cap['logicalProcessors']==64 and cap['physicalCores']==32 and cap['memoryBytes']>=500*q.plan.GIB and cap['freeMemoryBytes']>=32*q.plan.GIB,'Actual E64/outer reserve failed')
    for vol in snapshot['volumes']:
        b=value['admission']['volumeBudgets'][vol['letter']];require(vol['health']=='Healthy' and vol['free']>=b['freeFloorBytes'] and sum(b[k] for k in ('maximumVhdBytes','runtimeBytes','metadataBytes','freeFloorBytes'))<=vol['size'],'Actual unchanged volume/runtime reserve failed')
    placements=[x for n in snapshot['nodeCapacity'].values() for x in n['bridgePlacement'] if x['id'].lower()=='4c6ca5cc-8c9a-499b-8ffe-c029bbfd3522']
    require(len(placements)==1 and placements[0]['state']=='Running','Actual protected infrastructure VM not Running exactly once')
    if row['node']=='LB-NODE01' and row['effect'] not in ('drain','infrastructure-return','complete'):
        owner=placements[0]['hciNode'];require(owner in ('LB-NODE02','LB-NODE03') and snapshot['states'][owner]=='Running'
            and row['beforeProfiles'][owner]=={'cpu':20,'memory':96*1024**3},'Infrastructure not on admitted expanded survivor during NODE01 outage')
    if row['effect']=='complete':require(placements[0]['hciNode']=='LB-NODE01','Actual explicit infrastructure return not established')
    manifest={'identityDecision':binding['acceptance'],'mapTransportReceiptPath':binding['provenance']['transportReceiptPath'],
              'identityBindingSha256':binding['identityBindingSha256'],'factoryContractSha256':contract(),
              'continuityReceipts':proof.get('continuityReceipts',{}),'_actualCurrentReceiptSha256':proof['acceptedPreviousObserveReceiptSha256']}
    proxy=SimpleNamespace(PLAN_SHA=digest,ANCHOR=value['sourceCommit'],off_policy_sha=policy_sha,
                          map_from_transport=lambda path,decision:(binding['map'],binding['provenance']),read_transport=v4.read_transport)
    namespace=dict(guards.validate_identity.__globals__);namespace.update(c=proxy)
    lineage=FunctionType(guards.validate_identity.__code__,namespace)(value,snapshot,manifest,datetime.fromisoformat(proof['validatedAtUtc']))
    namespace=dict(guards.historical_off_basis.__globals__);namespace.update(c=proxy)
    historical=FunctionType(guards.historical_off_basis.__code__,namespace)
    limited=row['effect'] in ('cpu','memory','guest-start') and snapshot['states'][row['node']]=='Off'
    basis=historical(value,snapshot,row,proof.get('drainProof'),manifest,receipt) if limited else {}
    text=inspect.getsource(q.health)
    text=text.replace("ids[0] not in seen","(ids[0],job['name']) not in seen")
    text=text.replace("job['name']==plan.KNOWN[ids[0]]","job['name'] in (plan.KNOWN[ids[0]],plan.KNOWN[ids[0]].removesuffix('-Repair')+'-Regeneration')")
    text=text.replace('seen.add(ids[0])',"seen.add((ids[0],job['name']))")
    text=text.replace("('Suspended','Running') if returning or row['effect']=='guest-start'","('New','Suspended','Running') if returning or row['effect']=='guest-start'")
    if limited:
        before="require(all(d['maintenance'] is True for d in h['devices'] if d['owner']==node),'Current exact selected8 are not maintained')"
        require(text.count(before)==1,'Reviewed narrow Off maintenance boundary differs')
        text=text.replace(before,"require(_historical_verified,'Actual original pre-Stop/returned-Stop lineage missing')",1)
    namespace=dict(q.health.__globals__);namespace.update(SOURCE=value['sourceCommit'],PLAN_SHA=digest,_historical_verified=basis.get('lineageVerifiedHistoricalPreOffMaintenance',False))
    exec(compile(text,'<new-day-reviewed-health-with-exact-tuple-jobs>','exec'),namespace)
    context=namespace['health'](value,snapshot,row,proof.get('drainProof'))
    return {'health':{**context,**basis},'identityLineage':lineage,'pendingProtectionTransitions':pending}

def accept_after_read(value,completed_stage,path,pin,manifest,prior_proof,now):
    raw=Path(path).read_bytes();require(sha(raw)==pin,'Actual independent after-read SHA differs')
    receipt=json.loads(raw);o=receipt['result'];w=o['worker']
    require(receipt['status']=='complete' and receipt['sshExitCode']==0 and receipt['renderedSourceSha256']==manifest['observerSourceSha256']
            and receipt['strictPinnedHostKey'] is True and receipt['loopbackOnly'] is True and receipt['passwordAuthentication'] is False,
            'Exact new-day published independent observer/transport required')
    require(o['operationId']==OP and o['planSha256']==phase_digest(value) and o['stage']==completed_stage
            and o['workerAlive'] is False and o['workerSourceVerified'] is True and o['fullSnapshotsPerformed']==1
            and o['actualWorkerScriptBlockSha256']==manifest['workerScriptBlockSha256']
            and w['sourceSha256']==manifest['workerScriptBlockSha256'] and w['rpcReturned'] is True and w['phase']=='returned','Actual synchronous predecessor is unknown/wrong source')
    for at in (o['atUtc'],o['snapshot']['atUtc'],o['mocObservation']['atUtc']):
        stamp=datetime.fromisoformat(at.replace('Z','+00:00'));require(stamp.tzinfo is not None and 0<=(now-stamp).total_seconds()<=300,'Actual after-read stale/future; never restamp')
    sequence=list(stages());index=sequence.index(completed_stage)
    following=sequence[index+1] if index+1<len(sequence) else None
    proof=copy.deepcopy(prior_proof);proof.update(acceptedPreviousObserveReceiptSha256=pin,
        acceptedPreviousWorkerScriptBlockSha256=manifest['workerScriptBlockSha256'],validatedAtUtc=now.isoformat())
    if o.get('actualDrainProof') is not None:proof['drainProof']=o['actualDrainProof']
    refs=proof.setdefault('continuityReceipts',{})
    spec={'path':str(path),'transportReceiptSha256':pin,'sourceSha256':manifest['observerSourceSha256'],
          'script':receipt['script'],'transportSourceCommit':receipt['commit'],'businessSourceCommit':value['sourceCommit'],
          'acceptedByParent':True,'independentlySettled':True}
    # These are actual source-verified after-read results under the accepted phase,
    # not fabricated human approval or a generic new hash waiver.
    refs[completed_stage]=spec
    if value['transitionContract']['stages'][completed_stage]['effect'] in ('drain','moc-remove','guest-stop'):
        fields=('stage','key','planSha256','sourceCommit','pid','processStartedUtc','sequence','atUtc','futureIdentityBindingSha256')
        native_pin={k:w[k] for k in fields}
        native_pin.update(workerSha256=w['sourceSha256'],acceptedObserveTransportReceiptSha256=pin)
        if completed_stage.startswith('guest-stop-'):native_pin['preStopMaintenanceEvidence']=w['futurePreStopMaintenanceEvidence']
        proof.setdefault('continuity',{})[completed_stage]=native_pin
    if following:
        facts=check_snapshot(value,o['snapshot'],value['transitionContract']['stages'][following],proof,receipt)
        proof.update(facts)
    proof['actualPreviousNativeTimes']={'snapshot':o['snapshot']['atUtc'],'moc':o['mocObservation']['atUtc'],'observation':o['atUtc']}
    return {'nextStage':following,'proof':proof,'actualObservation':o}

def accept_projection(receipt_path,accepted_receipt_sha,projection):
    raw=Path(receipt_path).read_bytes();require(sha(raw)==accepted_receipt_sha,'Actual fresh baseline receipt SHA differs')
    receipt=json.loads(raw);o=receipt['result']
    require(receipt.get('status')=='complete' and receipt.get('sshExitCode')==0 and receipt.get('strictPinnedHostKey') is True
            and receipt.get('loopbackOnly') is True and receipt.get('passwordAuthentication') is False
            and receipt.get('renderedSourceSha256')==sha(capture_source().encode()),'Exact published new-day GET source/transport required')
    require(o['operationId']==OP and o['status']=='complete-new-day-healthy-identity-capture'
            and o['mutationPerformed'] is False,'Actual new-day all-healthy read required')
    require(projection.get('acceptedByParent') is True and projection.get('operationId')==OP
            and projection.get('actualReceiptSha256')==accepted_receipt_sha
            and projection.get('rawGuestsStaticSha256')==sha(canonical(o['snapshot']['guestsStatic']))
            and projection.get('publicProtectionSha256')==sha(canonical(o['publicProtection']))
            and projection.get('noProtectionMutationApproved') is True,'Actual current posture projection remains UNBOUND until parent acceptance')
    value=context();value['baseline']={k:copy.deepcopy(o['snapshot'][k]) for k in ('hostStatic','volumesStatic','clusterStatic','guestsStatic')}
    value['postNightlyProtectionProjection']=copy.deepcopy(projection)
    value['expectedPublicProtection']=copy.deepcopy(o['publicProtection'])
    value['initialNativeReceiptSha256']=accepted_receipt_sha
    value['initialActualSnapshotAtUtc']=o['snapshot']['atUtc']
    value['initialIdentityMap']=copy.deepcopy(o['identity'])
    # No GO is inferred from baseline acceptance. Parent supplies exact current phase/source/closure.
    return value

if __name__=='__main__':
    print(capture_source(),end='')
