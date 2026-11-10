"""Exact-plan whole-mirror maintenance qualification. Pure source/evidence assembly."""
import base64
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN_SHA = 'c6b4dfdfb3e1170129c8d578d3a87794d9ec41142275ed69c5decc2fb6006d53'
BASE_COMMIT = 'b8c4203c968c195786bef0f53f8d36e20f1ee8bd'
JOURNAL_SHA = 'b6ba06aa3f687077d2a1d22f045a3ad5eb58aca5f7f45f981836a84db162b807'
JOURNAL_PARENT_SHA = 'd452f3f312e3282ac2d36072225056dce3cbb898613c5722e8b90c8fa2073748'
OBSERVED_RECEIPT_SHA = 'a0b67964084181e43b9029b575652dc28b82e2c2930953f72eef644fd0443897'
PARENT_QUALIFICATION_SHA = '05ad4f03c92ed8b517648cd41b889806e8da89daa61ce93702b5ea9f99c3c1bb'
ROOT = r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-02'
POOL = '{923c0194-3ed4-449a-ae14-0f62861e0ec8}'
KNOWN = {'D82EEC019A25474789543A1796B552BB': 'UserStorage_1-Repair', '97F0D5071BB7314E9F51102237F77085': 'ClusterPerformanceHistory-Repair',
    '4C06845FA8C574499A937BD3EB57736A': 'UserStorage_2-Repair', '7C7DA96B2870124CADF176559F3F64F7': 'UserStorage_3-Repair', '9E5467C0BAC8834987723430C063E2C3': 'Infrastructure_1-Repair'}
JOBS_PIN = '7ae83365c2e5fbb032f4867edfb58d55880cd96a0d2e820d6ae222279f7dca03'
EVIDENCE_TEMPLATE_PIN = 'fb0f497052023fa758dd57c9a0360c35390a2ad1bbabcdc88ef295b99aafcfda'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def factory_sha():
    return sha(Path(__file__).read_bytes())


def require(value, message):
    if not value:
        raise ValueError(message)


def source(name, pin):
    raw = (HERE / name).read_bytes()
    require(sha(raw) == pin, 'Qualification dependency differs: ' + name)
    return raw.decode()


def parent_decision():
    raw = (HERE / 'parent-qualification.json').read_bytes()
    require(sha(raw) == PARENT_QUALIFICATION_SHA, 'Exact parent maintenance decision differs')
    decision = json.loads(raw)
    require(decision['planSha256'] == PLAN_SHA and decision['operationId'] == 'smal-foundation-profile-20261110-02' and decision['expiresAtSast'] == '2026-11-10T20:00:00+02:00' and decision['nativeReceiptSha256'] == OBSERVED_RECEIPT_SHA and decision['poolId'] == POOL and decision['qualifiedNativeJobNamesByVirtualDiskId'] == KNOWN, 'Parent qualification scope/tuple identity differs')
    require(all(decision[k] is True for k in ('freshNativeRecheckRequired', 'nextDrainAndCompletionRequireHealthyUpAndZeroJobs', 'originalPostReadFailedFlagPreserved', 'writeCurrentIndependentDrainProofAllowed')), 'Parent current-check/refusal requirements differ')
    require(all(decision[k] is False for k in ('originalDrainReplayAuthorised', 'originalPlanOrNativeHistoryRewriteAuthorised', 'physicalDeviceOnlyJobAttributionClaimed', 'unknownOrForeignJobsAllowed')), 'Parent qualification does not authorise replay, rewriting or attribution')
    require(decision['furtherOfflineActionsAllowedJobStates'] == ['Suspended'] and set(decision['compensatingReturnAllowedJobStates']) == {'Running', 'Suspended'}, 'Parent allowed job states differ')
    return decision


def validate_jobs(value, health, returning=False):
    parent_decision()  # Decision identity only, never current health or freshness.
    require(value['operationId'] == 'smal-foundation-profile-20261110-02' and value['maximumExecutionDeadline'] == '2026-11-10T20:00:00+02:00' and value['baseline']['clusterStatic']['poolId'] == POOL, 'Different qualification plan/pool/bound')
    seen = set()
    for job in health['activeStorageJobs']:
        ids = job['affectedVirtualDiskIds']
        require(len(ids) == 1 and ids[0] in KNOWN and job['name'] == KNOWN[ids[0]] and job['poolId'] == POOL and ids[0] not in seen, 'Unknown/foreign/duplicate whole-mirror repair association')
        seen.add(ids[0])
        require(job['state'] in (('Suspended', 'Running') if returning else ('Suspended',)), 'Job state not qualified for this exact maintenance phase')
        require(all(i is None or isinstance(i, str) and i in value['transitionContract']['deviceOwners'] for i in job['affectedDeviceIds']), 'Reported device outside exact existing 24')


def qualified_common(common):
    parent_decision()
    begin = common.index('    # No arbitrary job allowance.')
    end = common.index('\n}\n\nfunction Assert-ProfileInfrastructurePlacement', begin)
    old = common[begin:end]
    require("$job.name -ceq 'Repair'" in old and '$job.affectedDeviceIds.Count -gt 0' in old, 'Original job predicate differs')
    common = common[:begin] + "    # Parent-qualified exact whole-mirror repairs, with no physical attribution from null.\n    Assert-QualifiedMirrorJobs $h $compensating\n" + common[end:]
    return common.replace('function Assert-ComputeMaintenanceHealth(', source('mirror-jobs.ps1', JOBS_PIN) + '\nfunction Assert-ComputeMaintenanceHealth(', 1), old


def object_projection(bytes_name):
    # Do not round-trip the full snapshot through ConvertFrom-Json: native enum
    # projections retain both value/Value keys. Only remove the final JSON output.
    return "$text=[Text.Encoding]::UTF8.GetString(" + bytes_name + ")\n$needle=' | ConvertTo-Json -Depth 30 -Compress'\n$cut=$text.LastIndexOf($needle,[StringComparison]::Ordinal)\nif($cut -lt 0 -or $text.Substring($cut+$needle.Length) -cne \"`n} else { throw 'Corrected observer is GET-only' }`n\"){throw 'Known GET observer output boundary differs'}\n$objectSource=$text.Remove($cut,$needle.Length)\n$output=@(& ([ScriptBlock]::Create($objectSource)))\nif($output.Count -ne 1 -or $output[0] -isnot [Collections.IDictionary]){throw 'Original corrected observer object output incomplete'}\n$o=$output[0]\n"


def augment_observer(base_observer, stage, qualified=False):
    # Keep the original GET-only observer bytes inside one read-only output adapter.
    prefix = "$ErrorActionPreference='Stop'\n$bytes=[Convert]::FromBase64String('" + base64.b64encode(base_observer.encode()).decode() + "')\n"
    prefix += "$h=[Security.Cryptography.SHA256]::Create();try{$actual=[BitConverter]::ToString($h.ComputeHash($bytes)).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}\nif($actual -cne '" + sha(base_observer.encode()) + "'){throw 'Exact corrected GET observer changed'}\n"
    prefix += object_projection('$bytes')
    if qualified:
        prefix += "if($o.worker.maintenanceQualificationFactorySha256 -cne '" + factory_sha() + "'){throw 'Qualified worker provenance differs'}\n"
    prefix += "$o['maintenanceQualificationFactorySha256']='" + factory_sha() + "'\n$o['parentMaintenanceQualificationSha256']='" + PARENT_QUALIFICATION_SHA + "'\n$o['baseCorrectedObserverSha256']=$actual\n$o['observerOutputProjection']='Original GET object, final JSON only; native value/Value fields preserved'\n"
    node = stage[-9:] if stage.endswith(('LB-NODE01', 'LB-NODE02', 'LB-NODE03')) else 'LB-NODE01'
    prefix += "$statePath='" + ROOT + "\\worker-" + stage + ".state.json'\n$o['originalWorkerStateSha256']=(Get-FileHash -LiteralPath $statePath).Hash.ToLowerInvariant()\n"
    prefix += "$path='" + ROOT + "\\drain-proof-" + node + ".json'\n"
    prefix += "$proof=$null;$proofSha=$null\nif(Test-Path -LiteralPath $path){$f=Get-Item -LiteralPath $path;if($f.Length -gt 65536 -or ($f.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Supplemental drain proof path/size differs'};$p=[IO.File]::ReadAllBytes($path);$proof=[Text.Encoding]::UTF8.GetString($p)|ConvertFrom-Json;$h=[Security.Cryptography.SHA256]::Create();try{$proofSha=[BitConverter]::ToString($h.ComputeHash($p)).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}\n"
    prefix += "$o['supplementalDrainProof']=$proof\n$o['supplementalDrainProofSha256']=$proofSha\n$o|ConvertTo-Json -Depth 40 -Compress\n"
    return prefix


def qualify_capsule(journal_capsule, stage, mode, common):
    result = dict(journal_capsule)
    correction = {**journal_capsule['correction'], 'correction': dict(journal_capsule['correction']['correction'])}
    if stage == 'drain-LB-NODE02':
        require(mode == 'observe', 'Issued first drain is observe-only here')
        result['dispatcher'] = augment_observer(result['dispatcher'], stage)
        result['correction'] = correction
        return result
    qualified, old_jobs = qualified_common(common)
    original = result['worker']
    jobs = source('mirror-jobs.ps1', JOBS_PIN)
    require(original.count(old_jobs) == 1 and original.count('function Assert-ComputeMaintenanceHealth(') == 1, 'Unused worker original maintenance source differs')
    worker = original.replace(old_jobs, "    # Parent-qualified exact whole-mirror repairs, with no physical attribution from null.\n    Assert-QualifiedMirrorJobs $h $compensating\n", 1)
    worker = worker.replace('function Assert-ComputeMaintenanceHealth(', jobs + '\nfunction Assert-ComputeMaintenanceHealth(', 1)
    metadata = {'maintenanceQualificationFactorySha256': factory_sha(), 'maintenanceQualificationSourceReceiptSha256': OBSERVED_RECEIPT_SHA,
        'parentMaintenanceQualificationSha256': PARENT_QUALIFICATION_SHA,
        'maintenanceQualificationJournalWorkerSha256': sha(original.encode()),
        'maintenanceQualificationBasis': 'exact-known-same-pool-whole-mirror-repairs-no-null-device-attribution'}
    lines = ''.join("$state." + k + " = '" + v + "'\n" for k, v in metadata.items())
    worker = worker.replace('function Save-R2Worker(', lines + 'function Save-R2Worker(', 1)
    correction['journalOnlyWorkerSha256'] = correction['correctedWorkerSha256']
    correction['correctedWorkerSha256'] = sha(worker.encode())
    correction['worker'] = worker
    correction['correction'].update(metadata)
    result.update(worker=worker, correction=correction)
    if mode == 'dispatch':
        text = result['dispatcher']
        require(text.count("$workerSha256='" + journal_capsule['correction']['correctedWorkerSha256'].upper() + "'") == 1, 'Journal-corrected dispatcher hash binding differs')
        text = text.replace("$workerSha256='" + journal_capsule['correction']['correctedWorkerSha256'].upper() + "'", "$workerSha256='" + correction['correctedWorkerSha256'].upper() + "'", 1)
        old_payload = base64.b64encode(original.encode()).decode()
        require(text.count("$workerBase64='" + old_payload + "'") == 1, 'Journal-corrected dispatcher payload differs')
        result['dispatcher'] = text.replace("$workerBase64='" + old_payload + "'", "$workerBase64='" + base64.b64encode(worker.encode()).decode() + "'", 1)
    else:
        text = result['dispatcher']
        require(text.count("$workerSha256='" + journal_capsule['correction']['correctedWorkerSha256'].upper() + "'") == 1, 'Journal-corrected observer hash differs')
        text = text.replace("$workerSha256='" + journal_capsule['correction']['correctedWorkerSha256'].upper() + "'", "$workerSha256='" + correction['correctedWorkerSha256'].upper() + "'", 1)
        result['dispatcher'] = augment_observer(text, stage, qualified=True)
    return result


def evidence_source(value, original_corrected_observer, common):
    require(sha(original_corrected_observer.encode()) == '7ad2f3fae4dcf9005fb2d0714a167926fb11220a3881d481ce0cd69064c85821', 'Exact first corrected observer required')
    qualified, _ = qualified_common(common)
    helpers = common[common.index('function Assert-Compute('):common.index('function Read-ComputeGuestStatic')]
    maintenance = qualified[qualified.index('function Assert-QualifiedMirrorJobs'):qualified.index('function Assert-ComputeMaintenanceHealth')]
    maintenance += qualified[qualified.index('function Assert-ComputeMaintenanceHealth'):qualified.index('function Assert-ProfileInfrastructurePlacement')]
    template = source('evidence-first.ps1.in', EVIDENCE_TEMPLATE_PIN)
    fields = {'PURE_HELPERS': helpers, 'QUALIFIED_MAINTENANCE': maintenance, 'PLAN_BASE64': base64.b64encode(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).decode(),
        'OBSERVER_BASE64': base64.b64encode(original_corrected_observer.encode()).decode(), 'PLAN_SHA': PLAN_SHA, 'BASE_COMMIT': BASE_COMMIT,
        'FACTORY_SHA': factory_sha(), 'OBSERVED_RECEIPT_SHA': OBSERVED_RECEIPT_SHA, 'JOURNAL_SHA': JOURNAL_SHA, 'JOURNAL_PARENT_SHA': JOURNAL_PARENT_SHA,
        'PARENT_QUALIFICATION_SHA': PARENT_QUALIFICATION_SHA}
    fields['OBJECT_PROJECTION'] = object_projection('$observerBytes')
    for key, text in fields.items():
        template = template.replace('@@' + key + '@@', text)
    require('@@' not in template, 'Unfilled evidence source token')
    return template
