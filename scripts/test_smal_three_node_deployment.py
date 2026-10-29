"""Offline exact three-node/no-witness platform effects and verified identities."""
import copy
import json
from pathlib import Path
import runpy
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ThreeNodeDeploymentTests(unittest.TestCase):
    def helpers(self):
        return runpy.run_path(str(ROOT / 'scripts/smal-three-node-platform.py'), run_name='three_platform_test')

    def test_cloud_and_private_proofs_require_all_three_exact_successful_nodes(self):
        p = self.helpers()
        cloud = json.loads((ROOT / 'docs/deployment-2026-10-29/three-node-arc-verified.json').read_text())
        local = json.loads((ROOT / 'docs/deployment-2026-10-27/private-ssh-three-node-live-after-arc-20261029.json').read_text())
        p['verify_cloud'](cloud['arcMachines']); p['verify_local'](local)
        bad = copy.deepcopy(cloud['arcMachines']); bad[2]['identity']['principalId'] = 'other'
        with self.assertRaises(RuntimeError): p['verify_cloud'](bad)
        bad = copy.deepcopy(local); bad['result']['nodes'][2]['guest']['bootstrapStatus'] = 'Failed'
        with self.assertRaises(RuntimeError): p['verify_local'](bad)
        bad = copy.deepcopy(local); bad['result']['nodes'][2]['guest']['disks'][1]['style'] = 'GPT'
        with self.assertRaises(RuntimeError): p['verify_local'](bad)
        bad = copy.deepcopy(local); bad['result']['nodes'][0]['hostDisks'][4]['path'] = 'C:\\wrong.vhdx'
        with self.assertRaises(RuntimeError): p['verify_local'](bad)

    def test_current_ad_expiry_and_ou_proof_remain_required(self):
        p = self.helpers()
        local = json.loads((ROOT / 'docs/deployment-2026-10-27/private-ssh-three-node-live-after-arc-20261029.json').read_text())
        local['result']['ad'] = {'domain': 'ad.localbox.test', 'ou': 'OU=SMAL01,OU=AzureLocal,DC=ad,DC=localbox,DC=test', 'inheritanceBlocked': True,
                                 'lcm': {'user': 'lboxdeploy', 'enabled': True, 'expired': False, 'neverExpires': False, 'groupCount': 0}}
        p['verify_local'](local, require_ad=True)
        local['result']['ad']['lcm']['expired'] = True
        with self.assertRaises(RuntimeError): p['verify_local'](local, require_ad=True)

    def test_node03_role_preview_refuses_any_extra_principal_role_or_scope(self):
        p = self.helpers(); changes = []
        for index, (scope, principal, role) in enumerate(sorted(p['NODE03_EXPECTED'])):
            changes.append({'resourceId': scope + '/providers/Microsoft.Authorization/roleAssignments/synthetic-' + str(index), 'changeType': 'Create', 'after': {'type': 'Microsoft.Authorization/roleAssignments', 'properties': {'principalId': principal, 'scope': scope, 'roleDefinitionId': '/subscriptions/' + p['SUB'] + '/providers/Microsoft.Authorization/roleDefinitions/' + role}}})
        data = {'status': 'Succeeded', 'changes': changes}; p['validate_node03_preview'](data, set())
        for key, value in [('principalId','other'),('scope','/subscriptions/' + p['SUB']),('roleDefinitionId','/roles/Owner'),('principalType','User')]:
            bad = copy.deepcopy(data); bad['changes'][0]['after']['properties'][key] = value
            with self.assertRaises(RuntimeError): p['validate_node03_preview'](bad, set())
        bad = copy.deepcopy(data); bad['changes'].pop()
        with self.assertRaises(RuntimeError): p['validate_node03_preview'](bad, set())
        result = subprocess.run(['az','bicep','build','--file',str(ROOT / 'infra/bicep/localbox-node03-platform-roles.bicep'),'--stdout','--only-show-errors'], check=True, capture_output=True, text=True, timeout=90)
        self.assertTrue(all(row['type'] == 'Microsoft.Authorization/roleAssignments' for row in json.loads(result.stdout)['resources']))

    def test_three_node_derivation_has_no_witness_key_or_public_configuration(self):
        h = runpy.run_path(str(ROOT / 'scripts/derive-smal-three-node-cluster.py'), run_name='no_witness_derivation_test')
        built = h['build']()
        for name, value in built.items():
            self.assertEqual(value, json.loads((ROOT / 'infra/arm' / name).read_text()))
            text = json.dumps(value)
            self.assertNotIn('listKeys', text)
            self.assertNotIn('WitnessStorageKey', text)
            self.assertNotIn('stlboxwitweu4766ea', text)
            self.assertNotIn('publicNetworkAccess', text)
        settings = built['localbox-three-node-settings.json']
        self.assertEqual(len(settings['parameters']['arcNodeResourceIds']['defaultValue']), 3)
        self.assertEqual(settings['parameters']['witnessType']['allowedValues'], ['No Witness'])
        self.assertEqual(settings['parameters']['clusterWitnessStorageAccountName']['defaultValue'], '')
        self.assertEqual(len(settings['variables']['deploymentSecretsList']), 2)
        self.assertEqual(len(built['localbox-three-node-secrets.json']['resources']), 2)
        for network in settings['parameters']['storageNetworkList']['defaultValue']:
            self.assertEqual(len(network['storageAdapterIPInfo']), 3)
            self.assertEqual(network['storageAdapterIPInfo'][2]['physicalNode'], 'LB-NODE03')


if __name__ == '__main__': unittest.main()
