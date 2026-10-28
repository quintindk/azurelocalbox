"""Offline boundary tests for human-only official Arc device authentication."""
import base64
import json
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ArcConsoleTests(unittest.TestCase):
    def test_powershell_scripts_parse(self):
        for name in ['register-smal-node-console.ps1', 'install-smal-arc-console.ps1']:
            code = "$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile('" + str(ROOT / 'scripts' / name) + "',[ref]$t,[ref]$e);if($e.Count){$e|ForEach-Object Message;exit 1}"
            subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, timeout=30)

    def test_installer_only_delivers_pinned_console_and_approval(self):
        helpers = runpy.run_path(str(ROOT / 'scripts/smal-private-powershell.py'), run_name='console_render_test')
        data = helpers['render_arc_console']((ROOT / 'scripts/install-smal-arc-console.ps1').read_bytes(), (ROOT / 'scripts/register-smal-node-console.ps1').read_bytes(), (ROOT / 'docs/deployment-2026-10-28/cloud-apply-approval.json').read_bytes(), 'a' * 40)
        self.assertNotRegex(data, rb'__[A-Z_]+__')
        installer = (ROOT / 'scripts/install-smal-arc-console.ps1').read_text()
        self.assertNotIn('Invoke-AzStackHciArcInitialization', installer)
        self.assertNotIn('New-PSSession', installer)
        self.assertIn('registrationPerformed = $false', installer)

    def test_console_omits_owner_token_and_fences_repeated_registration(self):
        source = (ROOT / 'scripts/register-smal-node-console.ps1').read_text()
        self.assertIn("-TargetSolutionVersion '12.2610.1004.41'", source)
        self.assertIn('[IO.FileMode]::CreateNew', source)
        self.assertIn("[ValidateSet('LB-NODE01','LB-NODE02')]", source)
        self.assertIn('Get-ArcBootstrapStatus', source)
        for forbidden in ['-ArmAccessToken', 'Get-AzAccessToken', 'Start-Transcript', 'Install-Module', 'Register-AzResourceProvider', 'Set-NetFirewall', 'CredSSP', 'TrustedHosts']:
            self.assertNotIn(forbidden, source)

    def test_launcher_refuses_headless_authentication_capture(self):
        h = runpy.run_path(str(ROOT / 'scripts/register-smal-node-console.py'), run_name='human_console_test')
        with patch.object(h['sys'].stdin, 'isatty', return_value=False):
            with self.assertRaises(RuntimeError): h['require_tty']()
        source = (ROOT / 'scripts/register-smal-node-console.py').read_text()
        self.assertIn('return subprocess.run(args, timeout=7200).returncode', source)
        self.assertNotIn('get-access-token', source)
        self.assertIn("'-o'", (ROOT / 'scripts/smal-private-powershell.py').read_text())

    def test_installed_console_did_not_register_and_all_guest_private_paths_pass(self):
        proof = json.loads((ROOT / 'docs/deployment-2026-10-27/private-ssh-install-arc-console-20261028.json').read_text())
        self.assertEqual(proof['status'], 'complete')
        self.assertFalse(proof['result']['registrationPerformed'])
        self.assertFalse(proof['result']['consoleOutputCaptured'])
        self.assertEqual(proof['result']['status'], 'installed-not-invoked')
        snapshot = json.loads((ROOT / 'docs/deployment-2026-10-27/private-ssh-guest-platform-private-path-20261028.json').read_text())
        self.assertEqual(snapshot['status'], 'complete')
        self.assertEqual(len(snapshot['result']['guests']), 3)
        for guest in snapshot['result']['guests']:
            self.assertEqual(len(guest['platformPrivateEndpoints']), 3)
            self.assertTrue(all(x['privateDnsMatched'] and x['normalTlsHttpResponseVerified'] for x in guest['platformPrivateEndpoints']))
        self.assertFalse(snapshot['result']['registrationPerformed'])


if __name__ == '__main__':
    unittest.main()
