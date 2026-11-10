"""Focused offline continuation checks. Native-named calls are fixture functions."""
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import build
import plan

sys.path.append(str(build.CANONICAL / 'scripts/smal-rolling-profile-20261109'))
import test_profile as original_tests
import test_moc_phases as original_moc_tests


def fixture_stage(stage):
    value, proof, _ = original_tests.fixture_stage(stage)
    now = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)
    value['executionApproval']['expiresAt'] = plan.DEADLINE
    proof['observedAt'] = now.isoformat()
    proof['originalReconciliationSha256'] = plan.RECONCILIATION['coordinatorReconciliationSha256']
    return value, proof, now


original_moc_tests.fixture_stage = fixture_stage


def powershell(source, execute=False):
    with tempfile.TemporaryDirectory(dir='/tmp/opencode') as directory:
        path = Path(directory) / 'fixture.ps1'
        path.write_text(source)
        if execute:
            args = ['-File', str(path)]
        else:
            args = ['-Command', "$t=$null;$e=$null;[Management.Automation.Language.Parser]::ParseFile('" + str(path) + "',[ref]$t,[ref]$e)|Out-Null;if($e.Count){$e|Out-String;exit 1}"]
        return subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', *args], capture_output=True, text=True, timeout=30)


class ContinuationChecks(unittest.TestCase):
    def test_exact_unchanged_25_stages_and_no_inherited_go(self):
        spec = importlib.util.spec_from_file_location('original_plan_fixture', build.CANONICAL / 'scripts/smal-rolling-profile-20261109/plan.py')
        original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original)
        self.assertEqual(plan.stages(), original.stages())
        self.assertEqual(len(plan.stages()), 25)
        value = plan.candidate()
        self.assertEqual(value['operationId'], plan.OPERATION_ID)
        self.assertFalse(value['executionApproval']['parentGo'])
        self.assertIsNone(value['executionApproval']['expiresAt'])
        self.assertFalse(value['nativeEffectsApproved'])
        self.assertNotIn('memory-LB-NODE01', plan.stages())

    def test_reconciliation_deadline_and_freshness_refuse(self):
        value, proof, now = fixture_stage('drain-LB-NODE02')
        self.assertTrue(plan.execution_preflight(value, 'drain-LB-NODE02', proof, now))
        for field in plan.RECONCILIATION:
            broken = copy.deepcopy(value)
            broken['originalOperationReconciliation'][field] = 'wrong'
            with self.assertRaises(ValueError):
                plan.execution_preflight(broken, 'drain-LB-NODE02', proof, now)
        for key in ('originalOperationsReconciled', 'retainedRootsAbsent', 'volumeGrowthBudgetsFit', 'allHealthyNoJobs', 'localWindowsAuthorityVerified'):
            broken = copy.deepcopy(proof)
            broken[key] = False
            with self.assertRaises(ValueError):
                plan.execution_preflight(value, 'drain-LB-NODE02', broken, now)
        for expiry in ('2026-11-10T20:00:01+02:00', '2026-11-10T15:20:00+02:00'):
            broken = copy.deepcopy(value)
            broken['executionApproval']['expiresAt'] = expiry
            with self.assertRaises(ValueError):
                plan.execution_preflight(broken, 'drain-LB-NODE02', proof, now)
        broken = copy.deepcopy(proof)
        broken['observedAt'] = '2026-11-10T14:54:59+00:00'
        with self.assertRaises(ValueError):
            plan.execution_preflight(value, 'drain-LB-NODE02', broken, now)

    def test_delta_preserves_original_guards_and_rejects_all_old_roots(self):
        files, pins = build.render()
        worker = files['profile-worker-template.ps1']
        stage = files['profile-stage-template.ps1']
        self.assertIn("Original RPC outcome unresolved; returned/dead is not independent settlement", stage)
        for root in (build.OLD_ROOT, r'C:\ProgramData\AzureLocalBox\ComputeCapacity-20261108-01', r'C:\ProgramData\AzureLocalBox\ComputeCapacity-R2-20261108-01'):
            self.assertIn("'" + root + "'", stage)
        for token in ('Current selected eight devices', 'Graceful stop requires current paused node', 'Assert-ProfileInfrastructurePlacement', '-NodeName $node', 'GO expired before RPC', 'Native processor/version bounds differ', 'Physical start availability/outer reserve violated', 'MigrationType Live'):
            self.assertIn(token, worker + files['common-render-fragment.ps1'])
        self.assertIn(plan.DEADLINE, worker)
        self.assertNotIn(build.OLD_DEADLINE, worker)
        self.assertIn(plan.RECONCILIATION['coordinatorReconciliationSha256'], worker)
        self.assertEqual(pins['scripts/smal-rolling-profile-20261109/build.py'], build.LEGACY_BUILD_PIN)

    def test_baseline_is_get_only_bounded_and_runtime_only(self):
        source, pins = build.baseline()
        self.assertIn(plan.DEADLINE, source)
        self.assertIn(build.OLD_ROOT, source)
        self.assertIn(plan.ROOT, source)
        self.assertNotIn('2026-11-10T15:00:00+02:00', source)
        self.assertIn('memoryAssignedBytes = [long]$_.MemoryAssigned', source)
        static = source[source.index('function Read-ComputeGuestStatic'):source.index('function New-ComputeSession')]
        self.assertNotIn('memoryAssignedBytes', static)
        self.assertNotIn('Start-VM ', source)
        self.assertNotIn('& $command[0] -NodeName', source)
        self.assertEqual(pins['scripts/read-smal-rolling-profile-baseline.ps1'], build.BASELINE_PIN)
        result = powershell(source)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_capsule_parse_unsealed_refusal_and_observe_after_expiry(self):
        data = build.capsule(plan.candidate(), 'drain-LB-NODE02')
        for key in ('worker', 'dispatcher'):
            result = powershell(data[key])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = powershell(data[key], execute=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Unsealed profile', result.stderr)
        value = plan.candidate()
        value['executionApproval'] = {'parentGo': True, 'expiresAt': '2026-01-01T00:00:00+00:00'}
        self.assertIn("$mode='observe'", build.capsule(value, 'drain-LB-NODE02', 'a' * 40, 'observe')['dispatcher'])
        with self.assertRaises((ValueError, KeyError)):
            build.capsule(value, 'drain-LB-NODE02', 'a' * 40)
        old = copy.deepcopy(value)
        old['operationId'] = build.OLD_OPERATION
        with self.assertRaises(ValueError):
            build.capsule(old, 'drain-LB-NODE02', 'a' * 40, 'observe')

    def test_startup_exact_install_preserves_capsule_and_baseline_bytes(self):
        files, pins = build.render()
        startup = files['proposed-canonical-startup.ps1']
        original = (build.CANONICAL / 'scripts/start-smal-existing-guests.ps1').read_text()
        self.assertEqual(startup.count("$profileRoot='" + build.OLD_ROOT + "'"), 1)
        self.assertEqual(startup.count("$profileRoot='" + plan.ROOT + "'"), 1)
        self.assertIn(original[:original.index('    $targets = @(')], startup)
        before = build.capsule(plan.candidate(), 'drain-LB-NODE02')
        before_baseline = build.baseline()[0]
        with tempfile.TemporaryDirectory(dir='/tmp/opencode') as directory:
            root = Path(directory)
            for name in pins:
                if 'smal-rolling-profile-20261110/' in name:
                    continue
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((build.CANONICAL / name).read_bytes())
            target = root / 'scripts/read-smal-rolling-profile-baseline.ps1'
            target.write_bytes((build.CANONICAL / 'scripts/read-smal-rolling-profile-baseline.ps1').read_bytes())
            (root / 'scripts/start-smal-existing-guests.ps1').write_text(startup)
            with patch.object(build, 'CANONICAL', root):
                self.assertEqual(build.render()[0], files)
                after = build.capsule(plan.candidate(), 'drain-LB-NODE02')
                self.assertEqual(before['worker'], after['worker'])
                self.assertEqual(before['planSha256'], after['planSha256'])
                self.assertEqual(before_baseline, build.baseline()[0])

    def test_runtime_field_uses_actual_vm_property_not_startup_ram(self):
        common = build.render()[0]['common-render-fragment.ps1']
        line = next(line for line in common.splitlines() if 'guestsRuntime =' in line)
        source = "$vms=@([pscustomobject]@{Name='LB-NODE02';Id=[guid]'12a44e0c-cc08-4c4c-a812-fa0b56efdbc3';MemoryAssigned=123456;MemoryStartup=999999})\n$guests=@();$states=@{};$volumes=@();$hostStatic=@{};$hostCapacity=@{}\n$x=@{\n" + line + "\n}\nif($x.guestsRuntime[0].memoryAssignedBytes -ne 123456){throw 'Not actual runtime memory'}"
        result = powershell(source, execute=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_new_startup_gate_blocks_active_bad_completion_and_live_original_worker(self):
        startup = build.render()[0]['proposed-canonical-startup.ps1']
        begin = startup.index("    $profileRoot='" + plan.ROOT + "'")
        gate = startup[begin:startup.index('    $targets = @(', begin)]
        for case in ('closed', 'active', 'bad-completion', 'live-worker', 'profile-drift'):
            operation = {'operationId': plan.OPERATION_ID, 'active': case == 'active', 'planSha256': 'a' * 64, 'sourceCommit': 'b' * 40}
            closed = {'planSha256': ('c' if case == 'bad-completion' else 'a') * 64, 'sourceCommit': 'b' * 40,
                      'allHealthyAndOk': True, 'noActiveStorageJobs': True, 'allOriginalOperationsReconciled': True,
                      'finalProfiles': {'LB-NODE02': {'cpu': 20, 'memory': 96 * plan.GIB}}}
            source = "$ErrorActionPreference='Stop'\n$root='" + plan.ROOT + "'\n"
            source += "$operationJson='" + json.dumps(operation) + "'\n$closedJson='" + json.dumps(closed) + "'\n$case='" + case + "'\n"
            source += """
function Test-Path { param($LiteralPath) return $LiteralPath -ceq $root }
function Join-Path { param($Path,$ChildPath) return $Path+'\\'+$ChildPath }
function Get-Content { param($Path,[switch]$Raw) if($Path.EndsWith('operation.json')){return $operationJson};if($Path.EndsWith('completion.json')){return $closedJson};return '{"phase":"returned","pid":123,"processStartedUtc":"2026-11-10T12:00:00.0000000Z"}' }
function Get-ChildItem { param($Path,$Filter,[switch]$File) if($case -ceq 'live-worker'){[pscustomobject]@{FullName='fixture.state.json'}} }
function Get-Process { param($Id,$ErrorAction) [pscustomobject]@{StartTime=[datetime]::Parse('2026-11-10T12:00:00.0000000Z').ToUniversalTime()} }
function Get-VM { [pscustomobject]@{Name='LB-NODE02';ProcessorCount=$(if($case -ceq 'profile-drift'){8}else{20});MemoryStartup=96GB} }
# Windows PowerShell 5.1 retains JSON date strings. Match that behaviour in pwsh.
function ConvertFrom-Json { process { Microsoft.PowerShell.Utility\\ConvertFrom-Json -InputObject $_ -DateKind String } }
$blocked=$false
try {
""" + gate + "\n}catch{$blocked=$true}\nif($blocked -ne ($case -cne 'closed')){throw 'Wrong continuation startup decision: '+$case}"
            result = powershell(source, execute=True)
            self.assertEqual(result.returncode, 0, case + ': ' + result.stdout + result.stderr)


for _node in plan.ORDER:
    for _effect in ('moc-remove', 'moc-add'):
        setattr(ContinuationChecks, 'test_' + _effect.replace('-', '_') + '_' + _node.replace('-', '_'), original_moc_tests.phase_control(_node, _effect))


if __name__ == '__main__':
    unittest.main()
