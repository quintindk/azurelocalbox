"""Offline regression tests. Compiles locally, never validates/applies in Azure."""
import json
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class SmalHostTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(['az', 'bicep', 'build', '--file',
                                 str(ROOT / 'infra/bicep/main.smal-host.bicep'), '--stdout'],
                                text=True, capture_output=True, check=True)
        cls.template = json.loads(result.stdout)
        cls.resources = cls.template['resources']

    def test_only_host_vm_and_nic(self):
        self.assertCountEqual([r['type'] for r in self.resources],
                              ['Microsoft.Compute/virtualMachines', 'Microsoft.Network/networkInterfaces'])

    def test_no_public_ip_or_shared_network_write(self):
        nic = next(r for r in self.resources if r['type'] == 'Microsoft.Network/networkInterfaces')
        config = nic['properties']['ipConfigurations'][0]['properties']
        self.assertNotIn('publicIPAddress', config)
        subnet = config['subnet']['id']
        for expected in ['rg-smal-network-san-1', 'vnet-smal-san-1', 'snet-localbox-host']:
            self.assertIn(expected, subnet)
        self.assertNotIn('snet-private-endpoints', subnet)
        self.assertFalse(nic['properties']['enableIPForwarding'])

    def test_no_bootstrap_or_role_assignments(self):
        self.assertFalse(self.template['outputs']['bootstrapDeployed']['value'])
        for resource in self.resources:
            self.assertNotIn('/extensions', resource['type'])
            self.assertNotIn('roleAssignments', resource['type'])

    def test_credentials_secure_and_no_implicit_approval(self):
        params = self.template['parameters']
        self.assertEqual(params['adminPassword']['type'].lower(), 'securestring')
        self.assertNotIn('defaultValue', params['adminPassword'])
        self.assertNotIn('defaultValue', params['hostPlanApproved'])
        self.assertEqual(params['hostPlanApproved']['allowedValues'], [True])
        for name in ['adminUsername', 'imageVersion']:
            self.assertNotIn('defaultValue', params[name])
        self.assertNotIn('costCentre', params)
        self.assertNotIn('reviewOn', params)

    def test_image_is_immutable_and_no_bypass_tags(self):
        self.assertEqual(self.template['parameters']['imageVersion']['allowedValues'], ['26100.33674.261024'])
        tags = self.template['variables']['tags']
        self.assertNotIn('SecurityControl', tags)
        self.assertNotIn('CostControl', tags)
        self.assertEqual(tags['project'], 'smal-ai')
        self.assertNotIn('cost-centre', tags)
        self.assertNotIn('review-on', tags)

    def test_os_and_data_disks_are_retained(self):
        vm = next(r for r in self.resources if r['type'] == 'Microsoft.Compute/virtualMachines')
        self.assertEqual(vm['properties']['securityProfile']['securityType'], 'Standard')
        profile = vm['properties']['storageProfile']
        self.assertEqual(profile['osDisk']['diskSizeGB'], 1024)
        self.assertEqual(profile['osDisk']['deleteOption'], 'Detach')
        disk_copy = profile['copy'][0]
        self.assertEqual(disk_copy['name'], 'dataDisks')
        self.assertEqual(disk_copy['input']['diskSizeGB'], 256)
        self.assertEqual(disk_copy['input']['deleteOption'], 'Detach')
        self.assertIn('8', disk_copy['count'])

    def test_legacy_hook_stops_before_operations(self):
        hook = (ROOT / 'infra/hooks/preprovision.sh').read_text()
        stop = hook.index('\nexit 1\n')
        self.assertLess(stop, hook.index('az provider register'))
        self.assertLess(stop, hook.index('azd env set'))

    def test_owner_cost_identity_approval_does_not_open_network_gates(self):
        directory = ROOT / 'docs/deployment-2026-10-27'
        approval = json.loads((directory / 'owner-approvals.json').read_text())
        plan = json.loads((directory / 'plan.json').read_text())
        self.assertTrue(approval['hostCostProposalApproved'])
        self.assertEqual(plan['deploymentPrincipal']['approvedObjectId'],
                         approval['approvedExistingDeploymentPrincipalId'])
        self.assertTrue(plan['retailCostProposal']['approved'])
        self.assertFalse(approval['newRoleAssignmentsApprovedByThisMessage'])
        self.assertFalse(approval['networkEgressGateWaived'])
        self.assertFalse(approval['nestedNetworkGateWaived'])
        self.assertFalse(approval['securityGovernanceGateWaived'])
        self.assertFalse(plan['proposedHost']['bootstrap'])

    def test_apply_precheck_fails_closed_without_technical_approvals(self):
        result = subprocess.run(['python3', '-B', str(ROOT / 'scripts/check-smal-apply.py'), '--offline'],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        decision = json.loads(result.stdout)
        self.assertFalse(decision['readyToApply'])
        self.assertFalse(decision['azureApplyAttempted'])
        self.assertIn('versionMatchedSourceScopedEgressAndGovernanceAcceptance', decision['pending'])
        self.assertIn('nestedPrefixRoutingDnsAndReturnPathAgreement', decision['pending'])
        self.assertNotIn('host-cost-approval', decision['pending'])
        self.assertNotIn('hostCostApproval', decision['pending'])
        self.assertNotIn('matching-named-principal-approval', decision['pending'])

    def test_explicit_host_phase_does_not_authorise_bootstrap(self):
        result = subprocess.run(['python3', '-B', str(ROOT / 'scripts/check-smal-apply.py'),
                                 '--offline', '--phase', 'host-only'], text=True, capture_output=True)
        self.assertIn(result.returncode, [0, 2])
        decision = json.loads(result.stdout)
        pending = decision.get('pending', [])
        self.assertNotIn('versionMatchedSourceScopedEgressAndGovernanceAcceptance', pending)
        self.assertNotIn('nestedPrefixRoutingDnsAndReturnPathAgreement', pending)
        self.assertNotIn('costCentre', pending)
        self.assertNotIn('reviewOn', pending)
        self.assertFalse(self.template['outputs']['bootstrapDeployed']['value'])

    def test_runner_rejects_shared_network_preview_changes(self):
        helper = runpy.run_path(str(ROOT / 'scripts/deploy-smal-host.py'), run_name='host_runner_test')
        record = {'status': 'succeeded', 'result': {'status': 'Succeeded', 'changes': [{
            'changeType': 'Modify',
            'resourceId': '/subscriptions/8d3c4bb2-fdf8-4bca-bb92-e387bd4766ea/resourceGroups/rg-smal-network-san-1/providers/Microsoft.Network/virtualNetworks/vnet-smal-san-1',
        }]}}
        self.assertFalse(helper['allowed_preview'](record))

    def test_runner_redacts_secure_fields_and_literal_values(self):
        helper = runpy.run_path(str(ROOT / 'scripts/deploy-smal-host.py'), run_name='host_runner_test')
        dummy = 'synthetic-test-fixture-not-a-credential'
        value = {'adminPassword': {'value': dummy}, 'details': ['value=' + dummy],
                 'protectedSettings': {'test': dummy}}
        scrubbed = helper['sanitise'](value, dummy)
        self.assertNotIn(dummy, json.dumps(scrubbed))
        self.assertEqual(scrubbed['adminPassword'], '[redacted-secure-input]')

    def test_feature_must_be_registered_before_prepare_or_apply(self):
        helper = runpy.run_path(str(ROOT / 'scripts/deploy-smal-host.py'), run_name='host_runner_test')
        function = helper['verify_identity_and_empty_group']
        results = [
            {'id': helper['SUB'], 'tenantId': helper['TENANT']},
            {'id': helper['PRINCIPAL']},
            {'state': 'NotRegistered'},
        ]
        with patch.dict(function.__globals__, {'az_read': unittest.mock.Mock(side_effect=results)}):
            with self.assertRaisesRegex(RuntimeError, 'feature change needs approval'):
                function()


if __name__ == '__main__':
    unittest.main()
