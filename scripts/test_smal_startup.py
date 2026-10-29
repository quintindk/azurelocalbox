"""Offline daily-startup boundaries. Never starts Azure or Hyper-V machines."""
import copy
import json
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.h = runpy.run_path(str(ROOT / 'scripts/start-smal-localbox.py'), run_name='startup_test')
        self.scope = self.h['ensure_host'].__globals__

    def test_running_host_is_not_restarted(self):
        ready = {'power': 'PowerState/running', 'agentReady': True}
        record = {}
        with patch.dict(self.scope, az=Mock(), host_state=Mock(return_value=ready)):
            self.h['ensure_host'](ready, 60, record, Mock())
            self.scope['az'].assert_not_called()
        self.assertFalse(record['hostStartRequested'])

    def test_stopped_host_gets_exactly_one_start_then_waits(self):
        for power in ['PowerState/stopped', 'PowerState/deallocated']:
            initial = {'power': power, 'agentReady': False}
            ready = {'power': 'PowerState/running', 'agentReady': True}
            record = {}
            command = Mock()
            with patch.dict(self.scope, az=command, host_state=Mock(return_value=ready)):
                self.h['ensure_host'](initial, 60, record, Mock())
            command.assert_called_once_with(['vm', 'start', '--subscription', self.h['SUB'], '-g', self.h['RG'], '-n', self.h['HOST'], '--no-wait'])
            self.assertTrue(record['hostStartRequested'])

    def test_starting_host_is_observed_without_duplicate_request(self):
        ready = {'power': 'PowerState/running', 'agentReady': True}
        command = Mock()
        with patch.dict(self.scope, az=command, host_state=Mock(return_value=ready)):
            self.h['ensure_host']({'power': 'PowerState/starting', 'agentReady': False}, 60, {}, Mock())
        command.assert_not_called()

    def test_shutdown_transition_is_refused(self):
        command = Mock()
        with patch.dict(self.scope, az=command):
            for power in ['PowerState/stopping', 'PowerState/deallocating', 'unknown']:
                with self.assertRaises(RuntimeError):
                    self.h['ensure_host']({'power': power}, 60, {}, Mock())
        command.assert_not_called()

    def test_uncertain_start_is_not_repeated(self):
        command = Mock(side_effect=subprocess.TimeoutExpired('az', 90))
        record = {}
        with patch.dict(self.scope, az=command):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.h['ensure_host']({'power': 'PowerState/deallocated'}, 60, record, Mock())
        self.assertTrue(record['hostStartRequested'])
        self.assertEqual(command.call_count, 1)

    def test_wait_is_bounded_even_when_host_stays_down(self):
        state = {'power': 'PowerState/starting', 'agentReady': False}
        clock = Mock()
        clock.monotonic.side_effect = [0, 61]
        with patch.dict(self.scope, time=clock, host_state=Mock(return_value=state), az=Mock()):
            with self.assertRaises(TimeoutError):
                self.h['ensure_host'](state, 60, {}, Mock())
        clock.sleep.assert_not_called()

    def test_private_routes_required_not_vpn_active_label(self):
        scope = self.h['verify_private_route'].__globals__
        with patch.dict(scope, subprocess=Mock(check_output=Mock(return_value=json.dumps([{'dev': 'wlp195s0'}]))), socket=Mock()):
            with self.assertRaises(RuntimeError):
                self.h['verify_private_route']()
            scope['socket'].create_connection.assert_not_called()

    def test_exact_guest_set_and_heartbeat_required(self):
        good = {'status': 'complete', 'result': {'registrationInvoked': False, 'registrationMarkersChanged': False,
                'guests': [{'name': name, 'id': vm_id, 'after': 'Running', 'heartbeatReady': True}
                           for name, vm_id in self.h['GUESTS'].items()]}}
        self.h['verify_guest_result'](good)
        for field, value in [('id', 'wrong'), ('after', 'Off'), ('heartbeatReady', False)]:
            bad = copy.deepcopy(good)
            bad['result']['guests'][0][field] = value
            with self.assertRaises(RuntimeError):
                self.h['verify_guest_result'](bad)
        bad = copy.deepcopy(good)
        bad['result']['guests'].append(bad['result']['guests'][0])
        with self.assertRaises(RuntimeError):
            self.h['verify_guest_result'](bad)

    def test_guest_script_parses_and_does_not_change_bootstrap_or_autostart(self):
        path = ROOT / 'scripts/start-smal-existing-guests.ps1'
        command = "$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile('" + str(path) + "',[ref]$t,[ref]$e);if($e.Count){$e|ForEach-Object Message;exit 1}"
        subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', command], check=True, capture_output=True, timeout=30)
        source = path.read_text()
        for forbidden in ['Set-VM', 'Restart-VM', 'Remove-Item', 'Invoke-AzStackHciArcInitialization', 'New-VM']:
            self.assertNotIn(forbidden, source)
        self.assertIn("if ($before -ne 'Running') { Start-VM", source)
        self.assertLess(source.index("name = 'LB-DC01'"), source.index("name = 'LB-NODE01'"))
        self.assertIn('AddSeconds(240)', source)
        for vm_id in self.h['GUESTS'].values():
            self.assertIn(vm_id, source)


if __name__ == '__main__':
    unittest.main()
