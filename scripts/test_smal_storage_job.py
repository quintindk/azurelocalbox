import base64
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StorageJobTests(unittest.TestCase):
    def test_powershell_scripts_parse(self):
        for name in ['smal-storage-worker.ps1', 'start-smal-storage-job.ps1', 'read-smal-storage-job.ps1', 'inspect-smal-eval-media-access.ps1']:
            code = "$t=$null; $e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('" + str(ROOT / 'scripts' / name) + "',[ref]$t,[ref]$e); if($e.Count){$e | ForEach-Object Message; exit 1}"
            subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, text=True)

    def test_storage_mutations_follow_exact_identity_guards(self):
        worker = (ROOT / 'scripts/smal-storage-worker.ps1').read_text()
        self.assertLess(worker.index('Manifest differs'), worker.index('New-StoragePool'))
        self.assertLess(worker.index('Approved RAW data disk state changed'), worker.index('New-StoragePool'))
        self.assertIn('Where-Object UniqueId -CEQ $expected.guestUniqueId', worker)
        self.assertIn('$drive[0].SCSILogicalUnit -ne ($expected.lun + 1)', worker)
        self.assertIn('$physical[0].CanPool -ne $true', worker)
        self.assertIn('$disk[0].IsBoot -or $disk[0].IsSystem', worker)
        self.assertIn('$partition | Format-Volume', worker)
        self.assertIn('$cAfter.Size -ne $cBefore.Size', worker)
        self.assertNotIn('Get-PhysicalDisk -CanPool', worker)

    def test_single_instance_no_automatic_replay_or_cron(self):
        worker = (ROOT / 'scripts/smal-storage-worker.ps1').read_text()
        installer = (ROOT / 'scripts/start-smal-storage-job.ps1').read_text()
        self.assertIn('[IO.FileMode]::CreateNew', worker)
        self.assertIn(r'Global\AzureLocalBox-Storage-20261028-01', worker)
        self.assertIn('-MultipleInstances IgnoreNew', installer)
        self.assertNotIn('New-ScheduledTaskTrigger', installer)
        self.assertNotIn('RestartCount', installer)
        self.assertNotIn('-ExecutionPolicy Bypass', installer)
        self.assertIn('Storage job already exists', installer)

    def test_scope_and_manifest_are_explicit_and_never_cloud_or_nested_apply(self):
        manifest = json.loads((ROOT / 'docs/deployment-2026-10-28/storage-job-manifest.json').read_text())
        decisions = json.loads((ROOT / 'docs/deployment-2026-10-28/deployment-decisions.json').read_text())
        self.assertTrue(decisions['simpleStorageFormattingApproved'])
        self.assertEqual(len(manifest['disks']), 8)
        self.assertEqual({d['lun'] for d in manifest['disks']}, set(range(8)))
        for disk in manifest['disks']:
            self.assertEqual(disk['namespaceId'], disk['lun'] + 1)
            self.assertNotIn('OSDisk', disk['resourceId'])
        source = (ROOT / 'scripts/smal-storage-worker.ps1').read_text()
        for forbidden in ['Mount-DiskImage', 'New-VM', 'Start-VM', 'New-VMSwitch', 'New-NetNat',
                          'Connect-AzAccount', 'New-AzRoleAssignment', 'Add-MpPreference', 'Enable-WSManCredSSP']:
            self.assertNotIn(forbidden, source)

    def test_native_heartbeat_compiles_and_writes_only_its_public_status(self):
        worker = (ROOT / 'scripts/smal-storage-worker.ps1').read_text()
        csharp = re.search(r"Add-Type -TypeDefinition @'\n(.*?)\n'@", worker, re.S).group(1)
        encoded = base64.b64encode(csharp.encode()).decode()
        with tempfile.TemporaryDirectory(dir='/tmp/opencode') as directory:
            code = "$ErrorActionPreference='Stop'; Add-Type -TypeDefinition ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + encoded + "'))); [LocalBoxStorageHeartbeat]::Start('" + directory + "',$PID); try { $s=[Diagnostics.Stopwatch]::StartNew(); while(-not (Test-Path '" + directory + "/heartbeat.json') -and $s.Elapsed.TotalSeconds -lt 5){Start-Sleep -Milliseconds 10}; Get-Content '" + directory + "/heartbeat.json' -Raw } finally { [LocalBoxStorageHeartbeat]::Stop() }"
            result = subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, text=True, timeout=30)
            heartbeat = json.loads(result.stdout)
            self.assertEqual(set(heartbeat), {'processId', 'atUtc'})
            self.assertGreater(heartbeat['processId'], 0)
