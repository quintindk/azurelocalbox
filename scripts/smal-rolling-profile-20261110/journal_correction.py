"""One fixed-plan journal correction. Pure source assembly; never dispatches or mutates history."""
import base64
import hashlib
import json
from pathlib import Path
import re

PLAN_SHA='c6b4dfdfb3e1170129c8d578d3a87794d9ec41142275ed69c5decc2fb6006d53'
BASE_COMMIT='b8c4203c968c195786bef0f53f8d36e20f1ee8bd'
ORIGINAL_SHA='fd02e48b96d93b2631687808e92642d6a4d5ec44a0e2f2e8fc6e685ef95f4998'
PARENT_SHA='d452f3f312e3282ac2d36072225056dce3cbb898613c5722e8b90c8fa2073748'
LATEST_SHA='b14b0cb751a8de7cefa27b37dc011166093668ec4beb3bda9125597242487740'
ROOT=r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-02'
CORRECTION_ID='rolling02-nonempty-journal-backup-20261110-01'
OLD_WRITER="    if (Test-Path $statePath) { [IO.File]::Replace($tmp, $statePath, $null) } else { [IO.File]::Move($tmp, $statePath) }"
NEW_WRITER="    if (Test-Path $statePath) { $backup = $statePath + '.before-sequence-' + $state.sequence + '.' + $state.invocationAttempt + '.json'; if (Test-Path -LiteralPath $backup) { throw 'Journal backup already exists; no overwrite' }; [IO.File]::Replace($tmp, $statePath, $backup) } else { [IO.File]::Move($tmp, $statePath) }"
PINS={
 'operation.json':'a24e4946070b235be182a4e65767eef662902a30b9abde6431f2d6ffd5387ea5',
 'request-drain-LB-NODE02.json':'b988fb7f3f08a00c6e3d404ae9573721c750a7abd019bf8af6c061f93d776848',
 'launch-drain-LB-NODE02-returned.json':'014b724cd0db73b1754f32281f58174a4a1f205afcbf259728f2aa7c471aff89',
 'worker-drain-LB-NODE02.state.json':LATEST_SHA,
 'worker-drain-LB-NODE02-event-1.json':LATEST_SHA,
 'worker-drain-LB-NODE02-event-2.json':'34db457fd217264126d074d2106a154f30afcf97548955217bf87c6ff999ed10',
 'worker-drain-LB-NODE02-event-3.json':'5b45357115e1dfc23a1fe884a9f142618f6fc9de8b7d5a2fcc8cb2ab750b10ae',
 'resume-invocation-drain-LB-NODE02-01.json':'aebe6c816a9501a6c1b9b61e53cf1ac55741e34078811504c1fc6d456a954079',
 'resume-returned-drain-LB-NODE02-01.json':'711e5be66eb60b860630ac696e9e0be68c5b147df1270550a51ee3b23486ffb1',
}
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def bound_source(text):
    def field(name):
        found=re.findall(r"^\$"+name+r"='([^']+)'$",text,re.M)
        if len(found)!=1:raise ValueError('Exact original prefix missing: '+name)
        return found[0]
    if field('planSha')!=PLAN_SHA or field('sourceCommit')!=BASE_COMMIT:raise ValueError('Different issued plan/source')
    stage=field('stage')
    if field('effectKey')!=stage:raise ValueError('Different original stage/key')
    match=re.search(r"^\$plan=.*?FromBase64String\('([^']+)'\)",text,re.M)
    if not match:raise ValueError('Original immutable plan bytes missing')
    raw=base64.b64decode(match[1],validate=True);plan=json.loads(raw)
    if sha(raw)!=PLAN_SHA or plan['operationId']!='smal-foundation-profile-20261110-02' or plan['executionApproval']['expiresAt']!='2026-11-10T20:00:00+02:00' or stage not in plan['transitionContract']['stages'] or len(plan['transitionContract']['stages'])!=25:raise ValueError('Different operation/deadline/stage contract')
    return stage


def correct_worker(original, *, start_sequence=0):
    """Use 3 only for the adjudicated issued drain; unused future stages use 0."""
    stage=bound_source(original);oldsha=sha(original.encode())
    first=stage=='drain-LB-NODE02'
    if (first and (start_sequence!=3 or oldsha!=ORIGINAL_SHA)) or (not first and start_sequence!=0):raise ValueError('Only exact first pre-RPC failure may continue after event 3')
    if original.count(OLD_WRITER)!=1 or original.count('sequence = 0; rpcInvoked = $false')!=1:raise ValueError('Original journal source differs/already corrected')
    attempt='journal-fix-'+stage.lower()+'-01'
    factorysha=sha(Path(__file__).read_bytes())
    fields={'originalWorkerSha256':oldsha,'originalOperationSourceCommit':BASE_COMMIT,'journalCorrectionId':CORRECTION_ID,
        'journalCorrectionFactorySha256':factorysha,'invocationAttempt':attempt,'journalStartSequence':start_sequence,
        'journalBaseEventSequence':start_sequence,'journalBaseLatestStateSequence':1 if first else 0,
        'journalBaseLatestStateSha256':LATEST_SHA if first else None,'preRpcAdjudicationSha256':PARENT_SHA if first else None}
    metadata=''.join('$state.'+key+' = '+('$null' if value is None else str(value) if isinstance(value,int) else "'"+value+"'")+'\n' for key,value in fields.items())
    if first:
        metadata+="$claim=Get-Content (Join-Path $root 'journal-correction-invocation-drain-LB-NODE02-01.json') -Raw|ConvertFrom-Json\n"
        metadata+="if($claim.pid -ne $PID -or $claim.correctedWorkerSha256 -cne $state.sourceSha256.ToLowerInvariant() -or $claim.factorySha256 -cne '"+factorysha+"' -or $claim.parentReconciliationSha256 -cne '"+PARENT_SHA+"'){throw 'Exact authorised journal correction invocation missing'}\n"
    corrected=original.replace(OLD_WRITER,NEW_WRITER,1).replace('sequence = 0; rpcInvoked = $false','sequence = '+str(start_sequence)+'; rpcInvoked = $false',1)
    corrected=corrected.replace('function Save-R2Worker(',metadata+'function Save-R2Worker(',1)
    return {'stage':stage,'originalWorkerSha256':oldsha,'correctedWorkerSha256':sha(corrected.encode()),'worker':corrected,
        'remoteWorkerName':'worker-'+stage+'.journal-fixed-01.ps1','invocationAttempt':attempt,'factorySha256':factorysha,
        'startSequence':start_sequence,'firstAdjudicatedStage':first,'correction':fields}


def correct_observer(original, correction):
    if bound_source(original)!=correction['stage']:raise ValueError('Observer stage differs')
    oldsha=correction['originalWorkerSha256'].upper();newsha=correction['correctedWorkerSha256'].upper()
    if original.count("$workerSha256='"+oldsha+"'")!=1:raise ValueError('Original observer worker binding differs')
    # Keep the original observe branch, remove its unreachable dispatch branch and
    # embedded launch payload. This proposal is GET-only and never installs a worker.
    text=re.sub(r"^\$workerBase64='[^']*'\n",'',original,flags=re.M)
    cut=text.index("} elseif ($mode -ceq 'dispatch') {")
    text=text[:cut]+"} else { throw 'Corrected observer is GET-only' }\n"
    text=text.replace("$workerSha256='"+oldsha+"'","$workerSha256='"+newsha+"'",1)
    text=text.replace("$workerFile = Join-Path $root ('worker-' + $stage + '.ps1')","$workerFile = Join-Path $root '"+correction['remoteWorkerName']+"'",1)
    guard="    if ($worker -and ($worker.originalWorkerSha256 -cne '"+correction['originalWorkerSha256']+"' -or $worker.journalCorrectionFactorySha256 -cne '"+correction['factorySha256']+"' -or $worker.invocationAttempt -cne '"+correction['invocationAttempt']+"')) { throw 'Explicit corrected-source lineage differs' }\n"
    if correction['firstAdjudicatedStage']:
        guard+="    $claim=Read-R2Json (Join-Path $root 'journal-correction-invocation-drain-LB-NODE02-01.json')\n    if($claim.correctedWorkerSha256 -cne '"+correction['correctedWorkerSha256']+"' -or $claim.factorySha256 -cne '"+correction['factorySha256']+"' -or $claim.parentReconciliationSha256 -cne '"+PARENT_SHA+"'){throw 'Corrected observer invocation provenance differs'}\n"
        guard+="    if ((Get-FileHash -LiteralPath (Join-Path $root 'worker-drain-LB-NODE02.ps1')).Hash.ToLowerInvariant() -cne '"+ORIGINAL_SHA+"') { throw 'Original source changed' }\n"
        for name,value in PINS.items():
            if name.endswith('.state.json'):continue
            guard+="    if ((Get-FileHash -LiteralPath (Join-Path $root '"+name+"')).Hash.ToLowerInvariant() -cne '"+value+"') { throw 'Retained original evidence changed' }\n"
        backup='worker-drain-LB-NODE02.state.json.before-sequence-4.'+correction['invocationAttempt']+'.json'
        guard+="    if ($worker -and $worker.journalCorrectionId -ceq '"+CORRECTION_ID+"' -and (Get-FileHash -LiteralPath (Join-Path $root '"+backup+"')).Hash.ToLowerInvariant() -cne '"+LATEST_SHA+"') { throw 'Exact original latest-state backup missing/different' }\n"
    text=text.replace('    $profiles = @(',guard+'    $profiles = @(',1)
    text=text.replace("       sourceCommit = $sourceCommit; stage = $stage;", "       correctionFactorySha256 = '"+correction['factorySha256']+"'; originalWorkerSha256 = '"+correction['originalWorkerSha256']+"'; correctedWorkerPath = $workerFile; baseSourceCommit = $sourceCommit\n       sourceCommit = $sourceCommit; stage = $stage;",1)
    return text


def first_resume(correction):
    if not correction['firstAdjudicatedStage'] or correction['startSequence']!=3:raise ValueError('Not the exact adjudicated first stage')
    template=Path(__file__).with_name('resume-journal-first.ps1.in').read_text()
    values={'WORKER_SHA':correction['correctedWorkerSha256'],'WORKER_NAME':correction['remoteWorkerName'],
        'WORKER_BASE64':base64.b64encode(correction['worker'].encode()).decode(),'FACTORY_SHA':correction['factorySha256'],
        'PINS_BASE64':base64.b64encode(json.dumps(PINS,separators=(',',':')).encode()).decode(),
        'ATTEMPT':correction['invocationAttempt'],'PARENT_SHA':PARENT_SHA}
    for key,value in values.items():template=template.replace('@@'+key+'@@',value)
    if '@@' in template:raise ValueError('Unfilled correction template')
    return template
