"""Read-only deployment-readiness observer boundary tests."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/inspect-smal-guest-deployment-readiness.ps1'


class GuestReadinessTests(unittest.TestCase):
    def test_powershell_parses(self):
        code = "$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile('" + str(SOURCE) + "',[ref]$t,[ref]$e);if($e.Count){$e|ForEach-Object Message;exit 1}"
        subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, timeout=30)

    def test_observer_has_no_guest_or_cloud_apply(self):
        source = SOURCE.read_text()
        for forbidden in ['Activate(', '/ato', 'Install-WindowsUpdate', 'New-ADUser', 'New-ADOrganizationalUnit', 'Set-GPInheritance', 'Register-Az', 'Invoke-AzStackHciArcInitialization -', 'Get-AzAccessToken', 'Set-Date']:
            self.assertNotIn(forbidden, source)
        self.assertIn('New-PSSession -VMId $vm.Id', source)
        self.assertIn("-Role $target.role", source)
        self.assertIn('licenseStatus = $_.LicenseStatus', source)
        self.assertNotIn('partialKey =', source)
        self.assertIn('updateApplicabilityAssessed = $false', source)


if __name__ == '__main__':
    unittest.main()
