from pathlib import Path
import json
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NextStageTests(unittest.TestCase):
    def test_expansion_parses(self):
        path = ROOT / 'scripts/expand-smal-os-volume.ps1'
        code = "$t=$null; $e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('" + str(path) + "',[ref]$t,[ref]$e); if($e.Count){$e | ForEach-Object Message; exit 1}"
        subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, text=True)

    def test_only_existing_os_partition_can_expand(self):
        source = (ROOT / 'scripts/expand-smal-os-volume.ps1').read_text()
        self.assertIn("$disk.Size -ne 1TB", source)
        self.assertIn("-not $disk.IsBoot", source)
        self.assertIn('Resize-Partition -DriveLetter C -Size $supported.SizeMax', source)
        self.assertIn('Prior expansion exists. Inspect rather than repeat.', source)
        self.assertIn('$dataBefore -ne $dataAfter', source)
        for forbidden in ['Format-Volume', 'Initialize-Disk', 'Remove-Partition', 'New-Partition',
                          'New-StoragePool', 'New-VM', 'New-VMSwitch', 'Restart-Computer']:
            self.assertNotIn(forbidden, source)

    def test_vendor_module_is_not_treated_as_execution_approval(self):
        audit = json.loads((ROOT / 'docs/deployment-2026-10-27/module-execution-review.json').read_text())
        self.assertEqual(audit['version'], '1.0.8')
        self.assertFalse(audit['installedOrImportedOnNewHost'])
        self.assertTrue(audit['noSecurityWaiverInferred'])
        self.assertEqual(len(audit['findings']), 6)


if __name__ == '__main__':
    unittest.main()
