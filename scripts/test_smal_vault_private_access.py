"""Offline exact-role effect validation. No live role/secret operations."""
import copy
import json
from pathlib import Path
import runpy
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VaultPrivateAccessTests(unittest.TestCase):
    def test_role_template_cannot_change_public_access_or_grant_owner(self):
        result = subprocess.run(['az', 'bicep', 'build', '--file', str(ROOT / 'infra/bicep/localbox-vault-deployer-role.bicep'), '--stdout', '--only-show-errors'], check=True, capture_output=True, text=True, timeout=90)
        data = json.loads(result.stdout)
        self.assertEqual(len(data['resources']), 1)
        role = data['resources'][0]
        self.assertEqual(role['type'], 'Microsoft.Authorization/roleAssignments')
        self.assertIn('Microsoft.KeyVault/vaults', role['scope'])
        self.assertNotIn('publicNetworkAccess', result.stdout)
        self.assertIn('82f494a8-b9f5-46fc-b0f7-c70be0572a63', result.stdout)
        self.assertIn('b86a8fe4-44ce-4948-aee5-eccb2c155cd7', result.stdout)

    def test_preview_refuses_wider_scope_different_identity_or_role(self):
        h = runpy.run_path(str(ROOT / 'scripts/apply-smal-vault-deployer-role.py'), run_name='private_role_test')
        good = {'status': 'Succeeded', 'changes': [{'resourceId': h['VAULT'] + '/providers/Microsoft.Authorization/roleAssignments/synthetic', 'changeType': 'Create', 'after': {'type': 'Microsoft.Authorization/roleAssignments', 'properties': {'principalId': h['H']['PRINCIPAL'], 'principalType': 'User', 'roleDefinitionId': '/subscriptions/' + h['SUB'] + '/providers/Microsoft.Authorization/roleDefinitions/' + h['ROLE'], 'scope': h['VAULT']}}}]}
        h['validate_preview'](good)
        for key, value in [('principalId', 'other'), ('scope', '/subscriptions/' + h['SUB']), ('roleDefinitionId', '/roles/Owner')]:
            bad = copy.deepcopy(good); bad['changes'][0]['after']['properties'][key] = value
            with self.assertRaises(RuntimeError): h['validate_preview'](bad)
        bad = copy.deepcopy(good); bad['changes'][0]['changeType'] = 'Modify'
        with self.assertRaises(RuntimeError): h['validate_preview'](bad)

    def test_actual_preview_ignored_resources_are_unchanged_not_extra_writes(self):
        h = runpy.run_path(str(ROOT / 'scripts/apply-smal-vault-deployer-role.py'), run_name='actual_role_preview_test')
        data = json.loads((ROOT / 'docs/deployment-2026-10-28/vault-deployer-role-what-if.json').read_text())
        h['validate_preview'](data)
        ignored = next(x for x in data['changes'] if x['changeType'] == 'Ignore')
        ignored['after']['location'] = 'another-region'
        with self.assertRaises(RuntimeError): h['validate_preview'](data)


if __name__ == '__main__':
    unittest.main()
