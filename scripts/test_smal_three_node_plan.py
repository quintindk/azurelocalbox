"""Offline three-node sizing and read-only inventory boundaries."""
from pathlib import Path
import copy
import base64
import hashlib
from decimal import Decimal
import json
import runpy
import subprocess
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class ThreeNodePlanTests(unittest.TestCase):
    def test_exact_three_node_approval_hashes_and_public_context(self):
        out = ROOT / 'docs/deployment-2026-10-29'
        consent = json.loads((out / 'three-node-approval.json').read_text())
        self.assertTrue(consent['approved'])
        self.assertEqual(consent['humanAnswer'], 'Approved')
        for suffix, key in [('json', 'proposalJsonSha256'), ('md', 'proposalMarkdownSha256')]:
            self.assertEqual(hashlib.sha256((out / ('three-node-proposal.' + suffix)).read_bytes()).hexdigest(), consent[key])
        h = runpy.run_path(str(ROOT / 'scripts/smal-three-node-approval.py'), run_name='three_node_context_test')
        disk = {'id': h['DISK_ID'], 'uniqueId': '11111111-1111-4111-8111-111111111111', 'diskSizeGB': 2048, 'sku': {'name': 'Premium_LRS'}}
        context = h['context'](disk)
        self.assertEqual(base64.b64decode(context['approvalBase64']), (out / 'three-node-approval.json').read_bytes())
        self.assertEqual(context['lun'], 8)
        disk['diskSizeGB'] = 4096
        with self.assertRaises(RuntimeError): h['context'](disk)

    def test_new_disk_template_and_preview_cannot_modify_existing_storage(self):
        h = runpy.run_path(str(ROOT / 'scripts/apply-smal-three-node-disk.py'), run_name='new_disk_test')
        data = {'status': 'Succeeded', 'changes': [{'changeType': 'Create', 'resourceId': h['DISK_ID'], 'after': {'type': 'Microsoft.Compute/disks', 'location': 'southafricanorth', 'sku': {'name': 'Premium_LRS'}, 'properties': {'diskSizeGB': 2048, 'creationData': {'createOption': 'Empty'}, 'networkAccessPolicy': 'DenyAll', 'publicNetworkAccess': 'Disabled'}}}]}
        h['validate_preview'](data, set())
        for key, value in [('diskSizeGB', 4096), ('publicNetworkAccess', 'Enabled')]:
            bad = copy.deepcopy(data); bad['changes'][0]['after']['properties'][key] = value
            with self.assertRaises(RuntimeError): h['validate_preview'](bad, set())
        bad = copy.deepcopy(data); bad['changes'][0]['changeType'] = 'Modify'
        with self.assertRaises(RuntimeError): h['validate_preview'](bad, set())
        result = subprocess.run(['az', 'bicep', 'build', '--file', str(ROOT / h['TEMPLATE']), '--stdout', '--only-show-errors'], check=True, capture_output=True, text=True, timeout=90)
        template = json.loads(result.stdout)
        self.assertEqual(len(template['resources']), 1)
        self.assertEqual(template['resources'][0]['type'], 'Microsoft.Compute/disks')
        self.assertEqual(template['resources'][0]['properties']['diskSizeGB'], 2048)

    def test_new_disk_admission_scripts_parse_and_never_target_disk_zero_or_pool_format(self):
        for name in ['smal-three-node-prelude.ps1', 'prepare-smal-node03-disk.ps1', 'format-smal-node03-disk.ps1']:
            path = ROOT / 'scripts' / name
            code = "$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile('" + str(path) + "',[ref]$t,[ref]$e);if($e.Count){$e|ForEach-Object Message;exit 1}"
            subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, timeout=30)
        source = (ROOT / 'scripts/format-smal-node03-disk.ps1').read_text()
        self.assertIn('Initialize-Disk -UniqueId $record.windowsUniqueId', source)
        self.assertIn('$newPhysical.Count -eq 1', source)
        self.assertIn('$disk.IsBoot -or $disk.IsSystem', source)
        for forbidden in ['-DiskNumber 0', 'New-StoragePool', 'New-VirtualDisk', 'Clear-Disk', 'Resize-VirtualDisk']:
            self.assertNotIn(forbidden, source)

    def test_final_premium_reconciliation_keeps_three_node_plan_unapplied(self):
        receipt = json.loads((ROOT / 'docs/deployment-2026-10-29/premium-disk-conversion-reconciled-result.json').read_text())
        self.assertEqual(receipt['status'], 'complete-nine-existing-premium-disks-host-guests-storage-and-arc-verified')
        self.assertEqual(len(receipt['disks']), 9)
        self.assertTrue(all(row['sku'] == 'Premium_LRS' and row['state'] == 'Attached' for row in receipt['disks']))
        self.assertEqual(receipt['host'], {'power': 'PowerState/running', 'agentReady': True})
        self.assertEqual(len(receipt['guests']), 3)
        self.assertTrue(all(row['state'] == 'Running' for row in receipt['guests']))
        self.assertTrue(all(row['status'] == 'Connected' for row in receipt['arcMachines']))
        self.assertEqual(receipt['pool']['health'], 'Healthy')
        self.assertFalse(receipt['thirdNodePlanApplied'])
        self.assertFalse(receipt['platformReadinessVerified'])
        self.assertTrue(receipt['originalConversionAndStartupFailuresRetained'])

    def test_live_premium_conversion_preserved_existing_disk_identity_and_encryption(self):
        receipt = json.loads((ROOT / 'docs/deployment-2026-10-29/premium-disk-conversion-after-cli-reconciliation.json').read_text())
        self.assertEqual(len(receipt['diskEffects']), 9)
        self.assertEqual(len(receipt['disksAfter']), 9)
        self.assertTrue(all(row['sku'] == 'Premium_LRS' for row in receipt['disksAfter']))
        before = {row['id']: row for row in receipt['disksBefore']}
        for row in receipt['disksAfter']:
            for key in ['uniqueId', 'diskSizeGB', 'encryptionType', 'diskEncryptionSetId', 'securityType']:
                self.assertEqual(row.get(key), before[row['id']].get(key))
        self.assertFalse(receipt['newDisksCreated'])
        self.assertFalse(receipt['guestProfilesChanged'])
        # Preserve the truthful original restore failure. Later successful startup
        # is independent evidence, not a rewrite of the partial run receipt.
        self.assertEqual(receipt['phase'], 'restore-existing-host-and-guests')
        self.assertEqual(receipt['status'], 'failed-inspect-before-resume')
        restored = json.loads((ROOT / 'docs/deployment-2026-10-29/start-20261029-080708-7389325a.json').read_text())
        self.assertEqual(restored['status'], 'complete-host-and-three-guests-running-heartbeats-healthy')
    def test_entra_reads_omit_subscription_but_disk_commands_keep_it(self):
        h = runpy.run_path(str(ROOT / 'scripts/convert-smal-host-premium.py'), run_name='premium_cli_test')
        scope = h['az'].__globals__
        process = Mock(return_value=Mock(stdout='null'))
        with patch.dict(scope, subprocess=Mock(run=process)):
            h['az'](['ad', 'signed-in-user', 'show'])
            self.assertNotIn('--subscription', process.call_args.args[0])
            h['az'](['disk', 'list'])
            self.assertIn('--subscription', process.call_args.args[0])

    def test_proposed_three_node_capacity_and_premium_scope_are_bounded(self):
        h = runpy.run_path(str(ROOT / 'scripts/plan-smal-three-node.py'), run_name='three_node_plan_test')
        proposal = h['build']()
        self.assertFalse(proposal['ownerApproved'])
        self.assertFalse(proposal['hostResizeRequested'])
        self.assertEqual(proposal['hostSkuBeforeAndAfter'], 'Standard_E32s_v6')
        self.assertEqual(proposal['guestMemoryTotalBytes'], 196 * 1024**3)
        self.assertEqual(proposal['assignedVcpusTotal'], 26)
        self.assertTrue(all(x['memoryGiB'] == 64 and x['vcpus'] == 8 for x in proposal['guestTargetProfiles']))
        self.assertTrue(all(x['fits'] for x in proposal['volumeBudgets'].values()))
        self.assertEqual(len(proposal['diskConversions']), 9)
        self.assertTrue(all(x['skuAfter'] == 'Premium_LRS' for x in proposal['diskConversions']))
        self.assertEqual(proposal['newDisk']['sku'], 'Premium_LRS')
        self.assertEqual(proposal['newDisk']['sizeGiB'], 2048)
        self.assertFalse(proposal['newDisk']['joinExistingPool'])
        self.assertEqual(proposal['existingVhdRelocation']['lun'], 4)
        self.assertIsNone(proposal['newNode']['vmId'])
        self.assertIsNone(proposal['cloudDelta']['node03DataUniqueIdAllowlist'])
        self.assertEqual(proposal['cloudDelta']['witnessTypeParameter'], 'No Witness')
        self.assertFalse(proposal['cloudDelta']['witnessCredentialReadOrUpload'])
        costs = proposal['retailDiskCapacityUsdPerMonth']
        self.assertEqual(Decimal(costs['after']) - Decimal(costs['before']), Decimal(costs['delta']))
        self.assertEqual(Decimal(costs['additionalDisk']), Decimal('315.6'))
        for name, value in [('three-node-proposal.json', json.dumps(proposal, indent=2) + '\n'), ('three-node-proposal.md', h['markdown'](proposal))]:
            self.assertEqual((ROOT / 'docs/deployment-2026-10-29' / name).read_text(), value)

    def test_one_tib_addition_does_not_fit_full_virtual_growth_and_reserves(self):
        h = runpy.run_path(str(ROOT / 'scripts/plan-smal-three-node.py'), run_name='three_node_budget_test')
        self.assertFalse(h['budget'](1023 * 1024**3, 978 * 1024**3, 64 * 1024**3)['fits'])

    def test_premium_conversion_refuses_missing_foreign_resized_or_wrong_tier_disks(self):
        h = runpy.run_path(str(ROOT / 'scripts/convert-smal-host-premium.py'), run_name='premium_conversion_test')
        expected = json.loads((ROOT / 'docs/deployment-2026-10-29/three-node-premium-cloud-sizing.json').read_text())['disks']
        h['verify_disks'](expected, expected)
        premium = copy.deepcopy(expected)
        for row in premium: row['sku'] = 'Premium_LRS'
        h['verify_disks'](premium, expected, final=True)
        with self.assertRaises(RuntimeError): h['verify_disks'](expected, expected, final=True)
        for key, value in [('managedBy', '/other-vm'), ('diskSizeGB', 4096), ('sku', 'UltraSSD_LRS'), ('id', '/other-disk')]:
            bad = copy.deepcopy(expected); bad[0][key] = value
            with self.assertRaises(RuntimeError): h['verify_disks'](bad, expected)
        with self.assertRaises(RuntimeError): h['verify_disks'](expected[:-1], expected)

    def test_conversion_shutdown_is_graceful_and_never_resizes_or_formats(self):
        path = ROOT / 'scripts/stop-smal-guests-for-premium.ps1'
        code = "$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile('" + str(path) + "',[ref]$t,[ref]$e);if($e.Count){$e|ForEach-Object Message;exit 1}"
        subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, timeout=30)
        source = path.read_text()
        for forbidden in ['-TurnOff', '-Force', 'Set-VM', 'Format-Volume', 'Remove-VM', 'Resize-VHD']:
            self.assertNotIn(forbidden, source)
        script = (ROOT / 'scripts/convert-smal-host-premium.py').read_text()
        self.assertIn("'--sku', 'Premium_LRS'", script)
        self.assertNotIn("'disk', 'create'", script)
        self.assertNotIn("'--size-gb'", script)

    def test_capacity_inspection_parses_and_does_not_change_guests_or_storage(self):
        path = ROOT / 'scripts/inspect-smal-three-node-capacity.ps1'
        code = "$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile('" + str(path) + "',[ref]$t,[ref]$e);if($e.Count){$e|ForEach-Object Message;exit 1}"
        subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, timeout=30)
        source = path.read_text()
        for forbidden in ['Set-VM', 'Stop-VM', 'Resize-VHD', 'Move-VMStorage', 'Format-Volume', 'New-VHD', 'Remove-Item']:
            self.assertNotIn(forbidden, source)
        self.assertIn('mutationPerformed = $false', source)


if __name__ == '__main__':
    unittest.main()
