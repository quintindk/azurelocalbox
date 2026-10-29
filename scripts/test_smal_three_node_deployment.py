"""Offline exact three-node/no-witness platform effects and verified identities."""
import copy
import json
from pathlib import Path
import runpy
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ThreeNodeDeploymentTests(unittest.TestCase):
    def test_no_witness_stage_previews_are_exact_and_do_not_retain_secret_payloads(self):
        h = runpy.run_path(str(ROOT / 'scripts/deploy-smal-three-node-cluster.py'), run_name='three_cluster_stage_test')
        self.assertEqual(len(h['SECRET_NAMES']),2)
        self.assertEqual(h['NAME'],'smal-localbox01')
        self.assertLessEqual(len(h['NAME']),15)
        self.assertEqual(len(h['effects']('prerequisites')),4)
        for stage in ['secrets','prerequisites','validate','deploy']:
            rows = [{'resourceId':rid,'changeType':'Create','after':{'properties':{'value':'SYNTHETIC-SECRET'}}} for rid in h['effects'](stage)]
            good = {'status':'Succeeded','changes':rows}
            safe = h['check_preview'](stage,good,set())
            self.assertNotIn('SYNTHETIC-SECRET',json.dumps(safe))
            bad = copy.deepcopy(good); bad['changes'][0]['resourceId'] = h['VAULT']
            with self.assertRaises(RuntimeError): h['check_preview'](stage,bad,set())
        source = (ROOT / 'scripts/deploy-smal-three-node-cluster.py').read_text()
        self.assertNotIn("'storage','account','update'",source)
        self.assertNotIn("'storage', 'account', 'update'",source)
        self.assertIn("parameters = L['secret_parameters']()",source)

    def test_reported_service_success_is_required_not_just_arm_acceptance(self):
        h = runpy.run_path(str(ROOT / 'scripts/deploy-smal-three-node-cluster.py'), run_name='three_service_outcome_test')
        safe = h['safe_action']({'status':'Success','steps':[{'name':'check','status':'Success','exception':[],'description':'SYNTHETIC-SECRET'}]})
        self.assertNotIn('SYNTHETIC-SECRET',json.dumps(safe))
        self.assertTrue(h['service_passed']({'provisioningState':'Succeeded','action':safe}))
        for status in ['InProgress','Error',None]:
            bad = {'provisioningState':'Succeeded','action':{**safe,'status':status}}
            self.assertFalse(h['service_passed'](bad))
        bad = copy.deepcopy(safe); bad['steps'][0]['status'] = 'Error'
        self.assertFalse(h['service_passed']({'provisioningState':'Succeeded','action':bad}))
        safe = h['safe_action']({'status':'Success','steps':[{'name':'check','status':'Success','exception':['SYNTHETIC-SECRET']} ]})
        self.assertNotIn('SYNTHETIC-SECRET',json.dumps(safe))
        self.assertFalse(h['service_passed']({'provisioningState':'Succeeded','action':safe}))

    def test_live_node03_role_receipt_is_exact_and_preserves_original_seven(self):
        p = self.helpers()
        receipt = json.loads((ROOT / 'docs/deployment-2026-10-29/node03-platform-roles-receipt.json').read_text())
        self.assertEqual(receipt['status'],'complete-three-node03-scoped-roles')
        self.assertEqual(receipt['deploymentState'],'Succeeded')
        self.assertEqual({p['R']['binding'](row) for row in receipt['assignmentsReadback']},p['NODE03_EXPECTED'])
        self.assertTrue(p['R']['EXPECTED'] <= {p['R']['binding'](row) for row in receipt['assignmentsBefore']})
        self.assertFalse(receipt['subscriptionWideGrantRequested'])
        self.assertFalse(receipt['publicAccessChangeRequested'])

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
        self.assertEqual(settings['parameters']['clusterName']['defaultValue'],'smal-localbox01')
        for template in built.values():
            for parameter in template.get('parameters',{}).values():
                if isinstance(parameter.get('defaultValue'),str):
                    self.assertLessEqual(len(parameter['defaultValue']),parameter.get('maxLength',2**31))
        self.assertEqual(len(settings['variables']['deploymentSecretsList']), 2)
        self.assertEqual(len(built['localbox-three-node-secrets.json']['resources']), 2)
        for network in settings['parameters']['storageNetworkList']['defaultValue']:
            self.assertEqual(len(network['storageAdapterIPInfo']), 3)
            self.assertEqual(network['storageAdapterIPInfo'][2]['physicalNode'], 'LB-NODE03')


if __name__ == '__main__': unittest.main()
