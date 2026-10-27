"""Run an authorised, committed PowerShell script through loopback/private Bastion SSH.

This establishes a command transport, not permission to run arbitrary deployments.
Never put secrets in a script, argument or output. The private key stays local.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import runpy
import signal
import socket
import stat
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
H = runpy.run_path(str(ROOT / 'scripts/enable-smal-private-ssh.py'), run_name='ssh_transport_helpers')
BASE = H['H']
OUT = H['OUT']
VM_ID = f"/subscriptions/{BASE['SUB']}/resourceGroups/{BASE['RG']}/providers/Microsoft.Compute/virtualMachines/{BASE['VM']}"


def ssh_args(port, admin, encoded):
    return ['ssh', '-n', '-v', '-F', '/dev/null', '-T', '-p', str(port), '-i', str(H['KEY']),
            '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none', '-o', 'BatchMode=yes',
            '-o', 'PasswordAuthentication=no', '-o', 'KbdInteractiveAuthentication=no',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(H['KNOWN']),
            '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'HostKeyAlias=' + H['ALIAS'],
            '-o', 'HostKeyAlgorithms=ssh-ed25519', '-o', 'ConnectTimeout=15',
            '-o', 'ForwardAgent=no', '-o', 'ClearAllForwardings=yes',
            '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2',
            admin + '@127.0.0.1', 'powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand ' + encoded]


def main(script, name):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', name):
        raise RuntimeError('Invalid receipt name')
    target = OUT / f'private-ssh-{name}.json'
    if target.exists():
        raise RuntimeError('Operation receipt exists. Inspect rather than repeat.')
    path = (ROOT / script).resolve()
    if not path.is_relative_to(ROOT / 'scripts') or path.suffix != '.ps1':
        raise RuntimeError('Only reviewed scripts under repository scripts/ are accepted')
    relative = str(path.relative_to(ROOT))
    source = path.read_bytes()
    committed = subprocess.check_output(['git', 'show', 'HEAD:' + relative], cwd=ROOT)
    if committed != source:
        raise RuntimeError('Script differs from committed source')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    remote = subprocess.check_output(['git', 'ls-remote', '--heads', 'origin', 'refs/heads/' + branch], cwd=ROOT, text=True).split()
    if not remote or remote[0] != head:
        raise RuntimeError('Exact command source must be pushed')
    setup_path = OUT / 'private-ssh-setup-resume1.json'
    if not setup_path.exists():
        raise RuntimeError('Successful reconciled setup receipt missing')
    setup = json.loads(setup_path.read_text())
    if setup.get('status') != 'complete-host-key-pinned-login-not-yet-tested':
        raise RuntimeError('Successful setup evidence missing')
    if not H['KNOWN'].is_file() or H['KNOWN'].is_symlink() or stat.S_IMODE(H['KEY'].stat().st_mode) != 0o600:
        raise RuntimeError('Missing trust file or unsafe key permissions')
    H['pin_host_key'](setup['result']['hostPublicKey'])
    route = subprocess.run(['ip', '-j', 'route', 'get', '10.204.0.4'], capture_output=True, text=True, check=True)
    if json.loads(route.stdout)[0].get('dev') != 'tun0':
        raise RuntimeError('Actual VPN route is not present')
    with socket.create_connection(('10.204.0.4', 53), timeout=5):
        pass
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1', 0))
        port = reserve.getsockname()[1]
    encoded = base64.b64encode(source.decode('utf-8').encode('utf-16-le')).decode('ascii')
    record = {'beganAtSast': BASE['now'](), 'status': 'pending', 'commit': head, 'script': relative,
              'transport': 'VPN-private-Premium-Bastion-loopback-SSH22', 'strictPinnedHostKey': True,
              'passwordAuthentication': False, 'privateKeyValueExported': False}
    record['localPort'] = port
    with target.open('x') as stream:
        stream.write(json.dumps(record, indent=2) + '\n')
    command = ['az', 'network', 'bastion', 'tunnel', '--subscription', '702382d0-3722-4630-8983-5580b92f0c1a',
               '-g', 'rg-bastion-san-1', '-n', 'bas-test-san-1', '--target-resource-id', VM_ID,
               '--resource-port', '22', '--port', str(port), '--timeout', '300', '--only-show-errors']
    # Do not capture tunnel pipes: Azure CLI descendants can keep them open after
    # the parent exits. Isolate the process group and bound every cleanup wait.
    tunnel = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        deadline = time.monotonic() + 70
        while time.monotonic() < deadline and tunnel.poll() is None:
            listeners = subprocess.run(['ss', '-H', '-ltn', 'sport', '=', ':' + str(port)], capture_output=True, text=True, check=True).stdout.strip().splitlines()
            if listeners:
                if any('127.0.0.1:' + str(port) not in line for line in listeners):
                    raise RuntimeError('Bastion tunnel listener is not loopback-only')
                record['loopbackOnly'] = True
                break
            time.sleep(1)
        else:
            raise RuntimeError('Private Bastion tunnel not ready')
        result = subprocess.run(ssh_args(port, setup['result']['adminUser'], encoded), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=90)
        record['sshExitCode'] = result.returncode
        record['sshDiagnostics'] = {label: label in result.stderr for label in ['Server accepts key', 'Authenticated to', 'Sending command:', 'Exit status']}
        if result.returncode:
            labels = ['Host key verification failed', 'Permission denied', 'Connection timed out', 'Connection reset', 'Connection closed']
            record['errorLabel'] = next((label for label in labels if label in result.stderr), 'command-failed-raw-output-suppressed')
            record['status'] = 'failed-do-not-automatically-repeat'
        else:
            if re.search(r'-----BEGIN|\beyJ[A-Za-z0-9_-]{15,}\.|(?i:password|access_token|refresh_token)', result.stdout):
                raise RuntimeError('Unexpected sensitive-pattern output suppressed')
            record['result'] = json.loads(result.stdout)
            record['status'] = 'complete'
        target.write_text(json.dumps(record, indent=2) + '\n')
    except subprocess.TimeoutExpired as error:
        record['status'] = 'uncertain-command-timeout-do-not-repeat'
        diagnostic = error.stderr or b''
        if isinstance(diagnostic, bytes):
            diagnostic = diagnostic.decode(errors='replace')
        record['sshDiagnostics'] = {label: label in diagnostic for label in ['Server accepts key', 'Authenticated to', 'Sending command:', 'Exit status']}
    except (RuntimeError, ValueError) as error:
        record['status'] = 'failed-inspect-before-retry'
        record['errorType'] = type(error).__name__
    finally:
        try:
            os.killpg(tunnel.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            tunnel.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(tunnel.pid, signal.SIGKILL)
            tunnel.wait(timeout=5)
        # Tunnel diagnostics can contain signed URLs. Never export raw output.
        record['tunnelProcessClosed'] = True
        for _ in range(10):
            record['localSocketAbsent'] = not subprocess.run(['ss', '-H', '-ltn', 'sport', '=', ':' + str(port)], capture_output=True, text=True, check=True).stdout.strip()
            if record['localSocketAbsent']:
                break
            time.sleep(0.2)
        record['finishedAtSast'] = BASE['now']()
        target.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    return 0 if record['status'] == 'complete' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', required=True)
    parser.add_argument('--receipt', required=True)
    args = parser.parse_args()
    raise SystemExit(main(args.script, args.receipt))
