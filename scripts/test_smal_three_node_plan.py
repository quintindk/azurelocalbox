"""Offline three-node sizing and read-only inventory boundaries."""
from pathlib import Path
import copy
from decimal import Decimal
import json
import runpy
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ThreeNodePlanTests(unittest.TestCase):
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
