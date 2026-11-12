"""Inspect or repair the existing lab through its canonical private transport."""
import argparse
import base64
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import stat
import subprocess
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = {'inspect': 'Inspect', 'inspect-moc': 'InspectMoc', 'repair-moc': 'RepairMoc',
           'inspect-aks': 'InspectAks', 'inspect-node': 'InspectAksNode', 'inspect-access': 'InspectAccess',
            'inspect-performance': 'InspectPerformance', 'inspect-bridge': 'InspectBridge'}


def encoded(value):
    return base64.b64encode(json.dumps(value).encode()).decode()


def private_key(path):
    path = path.expanduser()
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Use the existing owner-only AKS SSH private key')
    public = subprocess.run(['ssh-keygen', '-y', '-P', '', '-f', str(path)],
                            capture_output=True, text=True, check=True, timeout=10).stdout.split()[:2]
    if public != Path(str(path) + '.pub').read_text().split()[:2]:
        raise ValueError('Existing AKS private/public key binding differs')
    return base64.b64encode(path.read_bytes()).decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=ACTIONS)
    parser.add_argument('--endpoint', action='append', default=[], help='Explicit nested IP:port for read-only connectivity checks')
    parser.add_argument('--vm-id', type=UUID)
    parser.add_argument('--vm-ip', type=ipaddress.IPv4Address)
    parser.add_argument('--api-ip', type=ipaddress.IPv4Address)
    parser.add_argument('--cluster-name')
    parser.add_argument('--ssh-key', type=Path)
    parser.add_argument('--bridge-kubeconfig', type=Path)
    parser.add_argument('--node-inspection', choices=('Basic', 'Bootstrap', 'Performance', 'ControlPlane', 'Kubernetes'), default='Basic')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    if not 30 <= args.timeout <= 3600:
        parser.error('Timeout must be between 30 and 3600 seconds')
    parameters = {'Action': ACTIONS[args.action],
                  'ConfigurationBase64': base64.b64encode((ROOT / 'config/smal-platform.json').read_bytes()).decode()}
    if args.endpoint:
        endpoints = []
        for value in args.endpoint:
            address, port = value.rsplit(':', 1)
            endpoints.append({'address': str(ipaddress.IPv4Address(address)), 'port': int(port)})
        parameters['DiagnosticEndpointsBase64'] = encoded(endpoints)
    if args.action == 'inspect-node':
        if not all((args.vm_id, args.vm_ip, args.cluster_name, args.ssh_key)):
            parser.error('Node inspection needs its observed VM ID/IP, cluster name and existing SSH key')
        parameters.update(AksVmId=str(args.vm_id), AksVmIp=str(args.vm_ip), AksClusterName=args.cluster_name,
                          SshPrivateKeyBase64=private_key(args.ssh_key), NodeInspection=args.node_inspection)
        if args.node_inspection == 'Kubernetes':
            if not args.api_ip:
                parser.error('Kubernetes inspection needs the configured private API IP for TLS verification')
            parameters['AksApiIp'] = str(args.api_ip)
    if args.action == 'inspect-bridge':
        if not args.bridge_kubeconfig or not args.cluster_name:
            parser.error('Bridge inspection needs the existing private kubeconfig and cluster name')
        path = args.bridge_kubeconfig.expanduser()
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            parser.error('Bridge kubeconfig must be an owner-only regular file')
        parameters.update(BridgeKubeconfigBase64=base64.b64encode(path.read_bytes()).decode(), AksClusterName=args.cluster_name)
    spec = importlib.util.spec_from_file_location('smal_private_transport', ROOT / 'scripts/smal-private-powershell.py')
    transport = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transport)
    return transport.main('scripts/smal-platform.ps1', parameters=parameters, timeout=args.timeout)


if __name__ == '__main__':
    raise SystemExit(main())
