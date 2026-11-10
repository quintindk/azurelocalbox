"""Offline continuation delta. No publication, transport, native execution or GO."""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import plan

CANONICAL = plan.CANONICAL
LEGACY_BUILD_PIN = '7bd4d626a8d208c43a8ee9a1604320d8f9dcf1f6267b75516ccd0c6742392290'
BASELINE_PIN = '6a7f3ef8c4a82d5d4c875047d76507f139be2387efae218819b20c6c9ff08568'
STARTUP_PIN = '657955dffbc22456863fe6360cc567adacc92e26d857904b20c26fbc5057face'
OLD_OPERATION = 'smal-foundation-profile-20261109-01'
OLD_ROOT = r'C:\ProgramData\AzureLocalBox\FoundationProfile-20261109-01'
OLD_DEADLINE = '2026-11-10T15:20:00+02:00'
BASELINE_PATH = 'scripts/read-smal-rolling-profile-baseline-20261110-02.ps1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Expected exactly one reviewed replacement: ' + before[:90])
    return text.replace(before, after, 1)


def legacy_builder():
    path = CANONICAL / 'scripts/smal-rolling-profile-20261109/build.py'
    if sha(path.read_bytes()) != LEGACY_BUILD_PIN:
        raise ValueError('Canonical input differs: original rolling builder')
    spec = importlib.util.spec_from_file_location('_smal_rolling_original_build', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CANONICAL = CANONICAL
    return module


def startup_delta(original):
    start = original.index("    $profileRoot='")
    end = original.index('    $targets = @(', start)
    old_gate = original[start:end]
    new_gate = old_gate.replace(OLD_ROOT, plan.ROOT).replace(OLD_OPERATION, plan.OPERATION_ID)
    return original[:end] + new_gate + original[end:]


def reconciliation_guard():
    lines = ["    if ($null -eq $plan.originalOperationReconciliation) { throw 'Exact original reconciliation missing' }"]
    for key, value in plan.RECONCILIATION.items():
        lines.append("    if ($plan.originalOperationReconciliation." + key + " -cne '" + value + "') { throw 'Original reconciliation binding differs: " + key + "' }")
    return '\n'.join(lines) + '\n'


def runtime_delta(common):
    # Runtime output is separate from guestsStatic and immutable profile equality.
    return replace_once(common, 'guestsStatic = $guests; states = $states;', 'guestsStatic = $guests; guestsRuntime = @($vms | ForEach-Object { @{ name = $_.Name; id = $_.Id.ToString(); memoryAssignedBytes = [long]$_.MemoryAssigned } }); states = $states;')


def render():
    legacy = legacy_builder()
    startup_path = CANONICAL / 'scripts/start-smal-existing-guests.ps1'
    installed = startup_path.read_text()
    installed_pin = sha(startup_path.read_bytes())
    # Permit the exact delta to be installed without altering future worker bytes.
    # Recover original bytes only by removing the exact new gate, then verify pin.
    if installed_pin != STARTUP_PIN:
        start = installed.index("    $profileRoot='" + plan.ROOT + "'")
        end = installed.index('    $targets = @(', start)
        original = installed[:start] + installed[end:]
        if sha(original.encode()) != STARTUP_PIN or startup_delta(original) != installed:
            raise ValueError('Canonical input differs: continuation startup interlock')
        legacy.BASE_RENDER_PINS = {**legacy.BASE_RENDER_PINS, 'proposed-canonical-startup.ps1': installed_pin}
        legacy.RENDER_PINS = {**legacy.RENDER_PINS, 'proposed-canonical-startup.ps1': installed_pin}
    else:
        original = installed
    files, pins = legacy.render()
    pins['scripts/smal-rolling-profile-20261109/build.py'] = LEGACY_BUILD_PIN
    pins['scripts/smal-rolling-profile-20261109/plan.py'] = plan.LEGACY_PLAN_PIN
    for name in ('build.py', 'plan.py'):
        pins['scripts/smal-rolling-profile-20261110/' + name] = sha((Path(__file__).parent / name).read_bytes())
    files['proposed-canonical-startup.ps1'] = startup_delta(original)
    for name in ('common-render-fragment.ps1', 'profile-worker-template.ps1', 'profile-stage-template.ps1'):
        text = files[name].replace(OLD_ROOT, plan.ROOT).replace(OLD_OPERATION, plan.OPERATION_ID).replace(OLD_DEADLINE, plan.DEADLINE)
        if name == 'common-render-fragment.ps1':
            text = runtime_delta(text)
        else:
            # A prior root is never a route into this fresh operation.
            text = replace_once(text, '    $clusterRead =' if name == 'profile-worker-template.ps1' else '    $mutex =', reconciliation_guard() + ('    $clusterRead =' if name == 'profile-worker-template.ps1' else '    $mutex ='))
            if name == 'profile-stage-template.ps1':
                text = replace_once(text, "foreach($oldRoot in @('C:\\ProgramData\\AzureLocalBox\\ComputeCapacity-20261108-01','C:\\ProgramData\\AzureLocalBox\\ComputeCapacity-R2-20261108-01'))", "foreach($oldRoot in @('C:\\ProgramData\\AzureLocalBox\\ComputeCapacity-20261108-01','C:\\ProgramData\\AzureLocalBox\\ComputeCapacity-R2-20261108-01','" + OLD_ROOT + "'))")
                text = replace_once(text, "    $mutex =", "    if ($plan.maximumExecutionDeadline -cne '" + plan.DEADLINE + "' -or [DateTimeOffset]::Parse($plan.executionApproval.expiresAt) -gt [DateTimeOffset]::Parse($plan.maximumExecutionDeadline)) { throw 'Continuation exceeds fixed phase bound' }\n    $mutex =")
        files[name] = text
    return files, pins


def baseline():
    path = CANONICAL / 'scripts/read-smal-rolling-profile-baseline.ps1'
    raw = path.read_bytes()
    if sha(raw) != BASELINE_PIN:
        raise ValueError('Canonical input differs: original GET baseline reader')
    files, pins = render()
    # The original reader embeds this exact, already pinned common fragment.
    # Its two surrounding fixed sections remain unchanged except explicit bounds/roots.
    source = raw.decode()
    begin = source.index('# Template only. Rendered stages')
    end = source.index('# Initial read only.', begin)
    embedded = source[begin:end].rstrip('\n') + '\n'
    if sha(embedded.encode()) != '0e58f64f888c897a48b1d4f28bd6faec22346e9d8f1c36e4c92da29f0a2b6b86':
        raise ValueError('Embedded original common source differs')
    common = files['common-render-fragment.ps1']
    source = source[:begin] + common + '\n' + source[end:]
    source = source.replace('2026-11-10T15:00:00+02:00', plan.DEADLINE)
    source = replace_once(source, "'" + OLD_ROOT + "') | ForEach-Object", "'" + OLD_ROOT + "', '" + plan.ROOT + "') | ForEach-Object")
    source = replace_once(source, "0e58f64f888c897a48b1d4f28bd6faec22346e9d8f1c36e4c92da29f0a2b6b86", sha(common.encode()))
    source = replace_once(source, "$entry = $null", "$entry = $null\n$continuationOperationId = '" + plan.OPERATION_ID + "'\n$originalReconciliationSha256 = '" + plan.RECONCILIATION['coordinatorReconciliationSha256'] + "'")
    source = replace_once(source, "readDeadline = $readDeadline.ToString('o');", "readDeadline = $readDeadline.ToString('o'); continuationOperationId = $continuationOperationId; originalReconciliationSha256 = $originalReconciliationSha256;")
    return source, {**pins, 'scripts/read-smal-rolling-profile-baseline.ps1': BASELINE_PIN}


def capsule(value, stage, source_commit='UNPUBLISHED', mode='dispatch'):
    # Same original capsule assembly and immutable-plan/proof split, new identity.
    if stage not in plan.stages() or mode not in ('dispatch', 'observe'):
        raise ValueError('Exact phase stage/mode required')
    if source_commit != 'UNPUBLISHED' and not re.fullmatch(r'[0-9a-f]{40}', source_commit):
        raise ValueError('Exact source checkpoint hash required')
    if value['operationId'] != plan.OPERATION_ID or value['guestIds'] != plan.IDS or value.get('originalOperationReconciliation') != plan.RECONCILIATION:
        raise ValueError('Exact new operation/VM/reconciliation binding required')
    if value['executionApproval']['parentGo'] is True:
        if source_commit == 'UNPUBLISHED':
            raise ValueError('No unpublished effect capsule')
        if mode == 'dispatch':
            plan.execution_preflight(value, stage, value['independentProof'])
    expected = plan.stages()[stage]
    if value['transitionContract']['stages'][stage] != expected:
        raise ValueError('Immutable stage/target delta differs')
    immutable = {key: item for key, item in value.items() if key != 'independentProof'}
    files, pins = render()
    raw = json.dumps(immutable, sort_keys=True, separators=(',', ':')).encode()
    digest = sha(raw)
    prefix = "$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + base64.b64encode(raw).decode() + "'))|ConvertFrom-Json)\n"
    prefix += "$stage='" + stage + "'\n$effectKey='" + expected['key'] + "'\n$planSha='" + digest + "'\n$sourceCommit='" + source_commit + "'\n"
    worker = prefix + files['common-render-fragment.ps1'] + '\n' + files['profile-worker-template.ps1']
    evidence = {'operationPlanSha256': digest, 'sourceCommit': source_commit, 'stage': stage, 'proof': value.get('independentProof')}
    evidence_sha = sha(json.dumps(evidence, sort_keys=True, separators=(',', ':')).encode())
    dispatch = prefix + "$mode='" + mode + "'\n$independentProofSha256='" + evidence_sha + "'\n$workerSha256='" + sha(worker.encode()).upper() + "'\n$workerBase64='" + base64.b64encode(worker.encode()).decode() + "'\n"
    dispatch += files['common-render-fragment.ps1'] + '\n' + files['profile-stage-template.ps1']
    return {'worker': worker, 'dispatcher': dispatch, 'planSha256': digest, 'sourcePins': pins, 'independentProof': evidence, 'independentProofSha256': evidence_sha}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('render', 'baseline', 'capsule'))
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--stage', choices=tuple(plan.stages()))
    parser.add_argument('--source-commit', default='UNPUBLISHED')
    parser.add_argument('--mode', choices=('dispatch', 'observe'), default='dispatch')
    args = parser.parse_args()
    if args.action == 'render':
        files, pins = render()
        result = {'files': files, 'sourcePins': pins, 'unsealedPlan': plan.candidate(), 'executionApproved': False}
    elif args.action == 'baseline':
        source, pins = baseline()
        result = {'files': {BASELINE_PATH: source}, 'sourcePins': pins, 'executionApproved': False}
    else:
        if args.plan is None or args.stage is None:
            parser.error('capsule requires --plan and --stage')
        result = capsule(json.loads(args.plan.read_text()), args.stage, args.source_commit, args.mode)
    print(json.dumps(result, indent=2))
