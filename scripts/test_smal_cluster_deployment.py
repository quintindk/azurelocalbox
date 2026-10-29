"""Offline deployment derivation, private secret-delivery and effect boundaries."""
import json
from pathlib import Path
import runpy
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ClusterDeploymentTests(unittest.TestCase):
    def test_derivation_matches_pinned_source_and_contains_only_bounded_resources(self):
        h = runpy.run_path(str(ROOT / 'scripts/derive-smal-cluster-templates.py'), run_name='derive_test')
        built = h['build']()
        for name, template in built.items():
            self.assertEqual(template, json.loads((ROOT / 'infra/arm' / name).read_text()))
            text = json.dumps(template)
            self.assertNotIn('publicNetworkAccess', text)
            self.assertNotIn('Microsoft.Storage/storageAccounts",', text)
        self.assertEqual(set(built['localbox-cluster-prerequisites.json']['resources']), {'edgeDevices', 'HCICluster'})
        settings = built['localbox-cluster-settings.json']
        self.assertEqual(set(settings['resources']), {'DeploymentSettings'})
        self.assertNotIn('localAdminPassword', settings['parameters'])
        data = settings['resources']['DeploymentSettings']['properties']['deploymentConfiguration']['scaleUnits'][0]['deploymentData']
        self.assertTrue(data['securitySettings']['hvciProtection'])
        self.assertTrue(data['securitySettings']['drtmProtection'])
        self.assertEqual(settings['parameters']['enableStorageAutoIp']['defaultValue'], False)
        self.assertEqual(settings['parameters']['euLocation']['defaultValue'], True)
        intents = settings['parameters']['intentList']['defaultValue']
        self.assertEqual([x['adapter'] for x in intents], [['MGMT1', 'MGMT2'], ['STORAGEA', 'STORAGEB']])
        self.assertTrue(all(x['adapterPropertyOverrides'] == {'networkDirect': 'Disabled', 'jumboPacket': '1514'} for x in intents))
        secrets = built['localbox-platform-secrets.json']
        self.assertEqual(len(secrets['resources']), 3)
        self.assertTrue(all(x['type'] == 'Microsoft.KeyVault/vaults/secrets' for x in secrets['resources']))
        self.assertTrue(all(x['type'] == 'securestring' for x in secrets['parameters'].values()))

    def test_private_input_and_sealing_scripts_parse_without_cloud_mutations(self):
        for name in ['inspect-smal-cluster-inputs.ps1', 'seal-smal-platform-credentials.ps1']:
            path = ROOT / 'scripts' / name
            code = "$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile('" + str(path) + "',[ref]$t,[ref]$e);if($e.Count){$e|ForEach-Object Message;exit 1}"
            subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, timeout=30)
            source = path.read_text()
            for forbidden in ['Format-Volume', 'Initialize-Disk', 'Set-LocalUser', 'Get-AzAccessToken', 'Start-Transcript', 'Set-ADUser']:
                self.assertNotIn(forbidden, source)
        seal = (ROOT / 'scripts/seal-smal-platform-credentials.ps1').read_text()
        self.assertIn('RSAEncryptionPadding]::OaepSHA256', seal)
        self.assertIn("-Role 'cluster-node-admin'", seal)
        self.assertIn("-Role 'deployment-user'", seal)
        self.assertIn('ZeroFreeBSTR', seal)
        self.assertNotIn('WriteAllText', seal)


if __name__ == '__main__':
    unittest.main()
