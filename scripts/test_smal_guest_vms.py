"""Offline VM helper guard tests, not a Hyper-V integration pass."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'scripts/smal-guest-vm-functions.ps1'


class GuestVmTests(unittest.TestCase):
    def test_library_parses_and_only_defines_function(self):
        code = "$t=$null;$e=$null;$a=[System.Management.Automation.Language.Parser]::ParseFile('" + str(LIBRARY) + "',[ref]$t,[ref]$e);if($e.Count){$e|ForEach-Object Message;exit 1};if(@($a.EndBlock.Statements).Count -ne 1 -or $a.EndBlock.Statements[0].GetType().Name -ne 'FunctionDefinitionAst'){exit 2}"
        subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, timeout=30)
        inspector = ROOT / 'scripts/inspect-smal-guest-cmdlets.ps1'
        code = "$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile('" + str(inspector) + "',[ref]$t,[ref]$e);if($e.Count){exit 1}"
        subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, timeout=30)

    def test_unapproved_guest_cannot_reach_hyperv(self):
        code = "$ErrorActionPreference='Stop';. '" + str(LIBRARY) + "';function New-VM {throw 'UNEXPECTED_MUTATION'};try{New-LabGuestVm -VmName 'OtherGuest' -GuardianName 'LB-LocalGuardian' -Checkpoint {param($phase)}}catch{if($_.Exception.Message -like '*UNEXPECTED_MUTATION*'){exit 2};exit 0};exit 3"
        subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', code], check=True, capture_output=True, timeout=30)

    def test_no_automatic_boot_or_unrelated_mutations(self):
        source = LIBRARY.read_text()
        self.assertIn('-AutomaticStartAction Nothing', source)
        self.assertIn('-CheckpointType Disabled', source)
        self.assertIn('-SecureBootTemplate MicrosoftWindows', source)
        self.assertIn('Enable-VMTPM -VM $vm', source)
        self.assertIn("-AllowedVlanIdList '0,711-712'", source)
        self.assertIn("$switch.SwitchType.ToString() -ne 'Internal'", source)
        self.assertIn('Get-VM -Id $vm.Id', source)
        for forbidden in ['Start-VM', 'Remove-VM', 'Stop-VM', 'Set-NetAdapter', 'Set-NetFirewall', 'Remove-Item', 'TrustedHosts', 'CredSSP']:
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
