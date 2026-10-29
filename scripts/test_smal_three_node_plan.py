"""Offline three-node sizing and read-only inventory boundaries."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ThreeNodePlanTests(unittest.TestCase):
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
