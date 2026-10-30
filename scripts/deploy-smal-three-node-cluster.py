"""Approved three-node No Witness deployment. Fixed per-stage identities, no replay.

Reuses the reviewed anonymous-memory RSA credential transport. Never enables
Shared Key/public access, reads a witness key, or treats ARM acceptance as service
validation success. Original two-node failures and receipts remain untouched.
"""
import argparse
import base64
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import runpy
import socket
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
P = runpy.run_path(str(ROOT / 'scripts/smal-three-node-platform.py'), run_name='three_node_cluster_platform')
L = runpy.run_path(str(ROOT / 'scripts/deploy-smal-cluster.py'), run_name='reviewed_cluster_crypto_and_reads')
T = runpy.run_path(str(ROOT / 'scripts/smal-private-powershell.py'), run_name='three_node_cluster_private_transport')
A, R, SUB, RG, SCOPE, VAULT, OUT = (P[key] for key in ['A','R','SUB','RG','SCOPE','VAULT','OUT'])
az = L['az']; API = L['API']
NAME = 'smal-localbox01'
CLUSTER = SCOPE + '/providers/Microsoft.AzureStackHCI/clusters/' + NAME
SETTINGS = CLUSTER + '/deploymentSettings/default'
TEMPLATES = {'secrets':'infra/arm/localbox-three-node-secrets.json', 'prerequisites':'infra/arm/localbox-three-node-prerequisites.json',
             'cluster-role':'infra/bicep/localbox-cluster-vault-role.bicep', 'validate':'infra/arm/localbox-three-node-settings.json', 'deploy':'infra/arm/localbox-three-node-settings.json'}
SECRET_NAMES = [NAME + '-LocalAdminCredential',NAME + '-AzureStackLCMUserCredential']


def source_guard():
    paths = [*set(TEMPLATES.values()), 'scripts/deploy-smal-three-node-cluster.py', 'scripts/smal-three-node-platform.py',
             'scripts/derive-smal-three-node-cluster.py', 'scripts/derive-smal-cluster-templates.py', 'scripts/deploy-smal-cluster.py',
             'scripts/apply-smal-arc-platform-roles.py',
             'scripts/seal-smal-platform-credentials.ps1', 'scripts/inspect-smal-three-node-live.ps1', 'scripts/smal-private-powershell.py',
             'docs/deployment-2026-10-29/three-node-local-identity-bindings.json', 'docs/deployment-2026-10-29/three-node-arc-verified.json']
    paths.append('docs/deployment-2026-10-29/cluster-name-correction-approval.json')
    head = A['source_guard'](paths)
    derived = runpy.run_path(str(ROOT / 'scripts/derive-smal-three-node-cluster.py'), run_name='three_node_cluster_derive_check')['build']()
    for name, value in derived.items():
        if json.loads((ROOT / 'infra/arm' / name).read_text()) != value: raise RuntimeError('Exact No Witness template derivation differs')
    for name in TEMPLATES.values():
        text = (ROOT / name).read_text()
        if 'listKeys' in text or 'WitnessStorageKey' in text: raise RuntimeError('Forbidden witness key effect in No Witness deployment')
    return head


def preflight():
    account = az(['account','show','--subscription',SUB])
    if account.get('id') != SUB or account.get('tenantId') != A['H']['TENANT'] or az(['ad','signed-in-user','show','--query','id']) != A['H']['PRINCIPAL']: raise RuntimeError('Approved identity/tenant/subscription differs')
    P['verify_cloud'](P['cloud_nodes']())
    roles = R['assignments']()
    if not P['ALL_EXPECTED'] <= {R['binding'](row) for row in roles}: raise RuntimeError('Ten inspected platform role bindings are not all present')
    if any(row['principalType'] != 'ServicePrincipal' for row in roles if R['binding'](row) in P['ALL_EXPECTED']): raise RuntimeError('Platform role principal type differs')
    addresses = {row[4][0] for row in socket.getaddrinfo('kv-lbox-weu-4766ea.vault.azure.net',443,family=socket.AF_INET)}
    if addresses != {'10.200.17.11'}: raise RuntimeError('Vault private DNS differs')
    for endpoint in [('10.204.0.4',53),('10.200.17.11',443)]:
        try:
            with socket.create_connection(endpoint,timeout=5): pass
        except OSError: raise RuntimeError('Actual private VPN TCP reachability failed before any stage action. Active profile/route alone is insufficient.') from None
    vault = az(['keyvault','show','--subscription',SUB,'-n','kv-lbox-weu-4766ea','--query','{id:id,pna:properties.publicNetworkAccess,rbac:properties.enableRbacAuthorization}'])
    if vault['id'].lower() != VAULT.lower() or vault['pna'] != 'Disabled' or vault['rbac'] is not True: raise RuntimeError('Expected private RBAC vault differs')


def inspect_inputs(stage,validated_ad_members=False):
    name = 'three-cluster-inputs-' + stage + '-20261029'
    with contextlib.redirect_stdout(io.StringIO()): code = T['main']('scripts/inspect-smal-three-node-live.ps1',name)
    path = T['OUT'] / ('private-ssh-' + name + '.json'); proof = json.loads(path.read_text())
    if code != 0: raise RuntimeError('Private current three-node input inspection failed')
    P['verify_local'](proof,require_ad=True,validated_ad_members=(stage == 'deploy' or validated_ad_members))
    print(json.dumps({'privateInspection':'passed','receipt':str(path.relative_to(ROOT))}),flush=True)
    return str(path.relative_to(ROOT))


def previous(stage):
    path = OUT / ('three-node-cluster-' + stage + '-receipt.json')
    reconciled = OUT / 'three-node-cluster-secrets-after-private-transport-reconciliation.json'
    if stage == 'secrets' and reconciled.exists(): path = reconciled
    validation_retry = OUT / 'three-node-cluster-validate-after-lcm-format-fix-receipt.json'
    if stage == 'validate' and validation_retry.exists(): path = validation_retry
    validation_observation = OUT / 'three-node-corrected-validation-observation.json'
    if stage == 'validate' and validation_retry.exists() and validation_observation.exists(): path = validation_observation
    gateway_retry = OUT / 'three-node-cluster-validate-after-gateway-echo-receipt.json'
    if stage == 'validate' and gateway_retry.exists(): path = gateway_retry
    gateway_reconciled = OUT / 'three-node-cluster-validate-gateway-after-auth-reconciliation-receipt.json'
    if stage == 'validate' and gateway_retry.exists() and gateway_reconciled.exists(): path = gateway_reconciled
    validation_success = OUT / 'three-node-cluster-validation-success-reconciliation-20261030.json'
    if stage == 'validate' and gateway_reconciled.exists() and validation_success.exists(): path = validation_success
    result = json.loads(path.read_text())
    if result.get('status') != 'complete' or result.get('deploymentState') != 'Succeeded': raise RuntimeError('Earlier three-node stage incomplete: ' + stage)
    return result


def effects(stage):
    if stage == 'secrets': return {(VAULT + '/secrets/' + name).lower() for name in SECRET_NAMES}
    if stage == 'prerequisites': return {CLUSTER.lower(), *((SCOPE + '/providers/Microsoft.HybridCompute/machines/' + node + '/providers/Microsoft.AzureStackHCI/edgeDevices/default').lower() for node in P['NODES'])}
    if stage in ['validate','deploy']: return {SETTINGS.lower()}
    return set()


def check_preview(stage,data,owned,principal=None):
    if data.get('status') != 'Succeeded': raise RuntimeError('No Witness what-if failed')
    seen = set(); result = []
    for row in data.get('changes',[]):
        kind = row.get('changeType'); rid = row.get('resourceId','').lower()
        if kind in ['NoChange','Ignore'] and rid in owned and row.get('before') == row.get('after'): continue
        if stage == 'cluster-role':
            after = row.get('after',{}); properties = after.get('properties',{})
            if kind != 'Create' or not rid.startswith(VAULT.lower() + '/providers/microsoft.authorization/roleassignments/') or after.get('type','').lower() != 'microsoft.authorization/roleassignments' or properties.get('principalId') != principal or properties.get('principalType') not in [None,'ServicePrincipal'] or properties.get('scope',VAULT).lower() != VAULT.lower() or properties.get('roleDefinitionId','').lower() != '/subscriptions/' + SUB + '/providers/microsoft.authorization/roledefinitions/4633458b-17de-408a-b874-0445c86b69e6':
                raise RuntimeError('Unlisted cluster identity/vault-only role effect')
        elif rid not in effects(stage) or kind not in (['Create','Modify'] if stage == 'deploy' else ['Create']): raise RuntimeError('Unlisted resource effect in No Witness stage: ' + stage)
        if rid in seen: raise RuntimeError('Duplicate preview effect')
        seen.add(rid); result.append({'id':row['resourceId'],'changeType':kind})
    if (stage == 'cluster-role' and len(seen) != 1) or (stage != 'cluster-role' and seen != effects(stage)): raise RuntimeError('Expected bounded No Witness effects missing')
    return result  # Never persist secret after-properties, even for marker previews.


def safe_action(action):
    if not isinstance(action,dict) or not isinstance(action.get('steps') or [],list): raise RuntimeError('Unexpected reported service status shape')
    return {'status':action.get('status'), 'steps':[{'name':step.get('name'), 'status':step.get('status'), 'index':step.get('fullStepIndex'),
            'exceptionCount':len(step.get('exception') or []), 'children':safe_action({'steps':step.get('steps') or []})['steps']} for step in action.get('steps',[]) or []]}


def service_result(stage):
    actual = L['rest'](SETTINGS); props = actual['properties']; expected_mode = 'Validate' if stage == 'validate' else 'Deploy'
    expected_ids = {(SCOPE + '/providers/Microsoft.HybridCompute/machines/' + name).lower() for name in P['NODES']}
    if actual['id'].lower() != SETTINGS.lower() or props.get('deploymentMode') != expected_mode or {rid.lower() for rid in props.get('arcNodeResourceIds',[])} != expected_ids: raise RuntimeError('Service mode/node resource binding differs')
    reported = props.get('reportedProperties') or {}
    key = 'validationStatus' if stage == 'validate' else 'deploymentStatus'
    units = (props.get('deploymentConfiguration') or {}).get('scaleUnits') or []
    data = units[0].get('deploymentData',{}) if len(units) == 1 else {}
    ad_verified = (data.get('domainFqdn') == 'ad.localbox.test'
                   and data.get('adouPath') == 'OU=SMAL01,OU=AzureLocal,DC=ad,DC=localbox,DC=test')
    return {'provisioningState':props.get('provisioningState'), 'mode':props.get('deploymentMode'),
            'adConfigurationVerified':ad_verified,'action':safe_action(reported.get(key) or {})}


def service_passed(result):
    steps = result.get('action',{}).get('steps',[])
    # Local Identity with Key Vault is an alternative to AD, not this deployment's
    # identity model. Permit only its exact inapplicable validation leaf. Never
    # accept arbitrary skipped checks or a skipped Deploy step.
    ad_passed = any(step.get('name') == 'Azure Local External Active Directory' and step.get('index') == '20'
                    and str(step.get('status','')).lower() in ['success','succeeded'] and step.get('exceptionCount',0) == 0 for step in steps)
    allow_identity_skip = result.get('mode') == 'Validate' and result.get('adConfigurationVerified') is True and ad_passed
    def good_steps(items,top=False):
        for step in items:
            if step.get('exceptionCount',0) != 0: return False
            status = str(step.get('status','')).lower()
            if status not in ['success','succeeded']:
                if not (top and allow_identity_skip and status == 'skipped' and step.get('name') == 'Azure Local Local Identity Validation'
                        and step.get('index') == '120' and not step.get('children')): return False
            if not good_steps(step.get('children',[])): return False
        return True
    return (result.get('provisioningState') == 'Succeeded' and str(result.get('action',{}).get('status','')).lower() in ['success','succeeded']
            and bool(steps) and good_steps(steps,top=True))


def normalise_lcm_parameters(parameters):
    raw = base64.b64decode(parameters['domainCredential']['value'],validate=True)
    qualified = b'LOCALBOX\\lboxdeploy:'; unqualified = b'lboxdeploy:'
    if raw.startswith(qualified): raw = unqualified + raw[len(qualified):]
    if not raw.startswith(unqualified) or len(raw) != len(unqualified) + 40: raise RuntimeError('Unexpected dedicated LCM username/credential format')
    return {**parameters,'domainCredential':{'value':base64.b64encode(raw).decode()}}


def verify_unsubmitted_secret_resume(prior,sealed_receipt_exists,template_hash):
    if (prior.get('stage') != 'secrets' or prior.get('status') != 'uncertain-or-still-running-inspect-do-not-repeat'
            or prior.get('deploymentName') != 'localbox-three-node-secrets-20261029' or 'deploymentId' in prior
            or 'deploymentState' in prior or prior.get('templateSha256') != template_hash or sealed_receipt_exists
            or {row['id'].lower() for row in prior.get('previewChanges',[])} != effects('secrets')):
        raise RuntimeError('No exact before-sealing, unsubmitted secret attempt is eligible for reconciliation')


def main(stage,wait_seconds=1200,resume_unsubmitted=False):
    head = source_guard(); action = 'localbox-three-node-' + stage + '-20261029'; path = OUT / ('three-node-cluster-' + stage + '-receipt.json')
    record = {'beganAtUtc':datetime.now(timezone.utc).isoformat(),'sourceCommit':head,'stage':stage,'deploymentName':action,'status':'pending',
              'witnessKeyReadOrUpload':False,'publicAccessChangeRequested':False,'sharedKeyChangeRequested':False,'subscriptionWideGrantRequested':False,'platformReadinessVerified':False}
    if resume_unsubmitted:
        if stage != 'secrets': raise RuntimeError('Only the exact unsubmitted secret stage can use this reconciliation')
        original_path = path; prior_bytes = original_path.read_bytes()
        if prior_bytes != subprocess.check_output(['git','show','HEAD:' + str(original_path.relative_to(ROOT))],cwd=ROOT): raise RuntimeError('Original unsubmitted secret receipt must be committed and retained')
        prior = json.loads(prior_bytes)
        verify_unsubmitted_secret_resume(prior,(T['OUT'] / 'private-ssh-sealed-platform-credentials-20261029.json').exists(),hashlib.sha256((ROOT / TEMPLATES['secrets']).read_bytes()).hexdigest())
        path = OUT / 'three-node-cluster-secrets-after-private-transport-reconciliation.json'
        record['originalPreSubmitRefusalRetained'] = True; record['originalReceiptSha256'] = hashlib.sha256(prior_bytes).hexdigest()
    with path.open('x') as stream: stream.write(json.dumps(record,indent=2) + '\n')
    def save(): path.write_text(json.dumps(record,indent=2) + '\n')
    parameters = None
    try:
        preflight()
        if az(['deployment','group','list','--subscription',SUB,'-g',RG,'--query',"[?name=='" + action + "'].name"]): raise RuntimeError('Exact stage deployment exists. Inspect, do not replay.')
        principal = None
        if stage == 'secrets':
            record['privateInputsReceipt'] = inspect_inputs('secrets-pre-submit-resume' if resume_unsubmitted else stage)
            active = az(['keyvault','secret','list','--subscription',SUB,'--vault-name','kv-lbox-weu-4766ea','--query','[].name'])
            deleted = az(['keyvault','secret','list-deleted','--subscription',SUB,'--vault-name','kv-lbox-weu-4766ea','--query','[].name'])
            if set(SECRET_NAMES) & (set(active) | set(deleted)): raise RuntimeError('Platform credential secret already exists. No overwrite/recovery/version replay.')
            parameters = {'localCredential':{'value':'NON-CREDENTIAL-PREVIEW'},'domainCredential':{'value':'NON-CREDENTIAL-PREVIEW'}}
        elif stage == 'prerequisites':
            previous('secrets'); record['privateInputsReceipt'] = inspect_inputs(stage)
            ids = {rid.lower() for rid in az(['resource','list','--subscription',SUB,'-g',RG,'--query','[].id'])}
            if effects(stage) & ids: raise RuntimeError('Cluster/edge prerequisites already exist. Reconcile instead of recreating.')
        elif stage == 'cluster-role':
            previous('prerequisites'); actual = L['rest'](CLUSTER)
            if actual['id'].lower() != CLUSTER.lower() or actual['location'] != 'westeurope' or actual['identity']['tenantId'] != A['H']['TENANT'] or actual['identity']['type'] != 'SystemAssigned': raise RuntimeError('Created cluster identity/region differs')
            principal = str(uuid.UUID(actual['identity']['principalId'])); record['inspectedClusterIdentity'] = actual['identity']
            if any(row['principalId'] == principal and row['roleDefinitionId'].endswith('/4633458b-17de-408a-b874-0445c86b69e6') for row in R['assignments']()): raise RuntimeError('Equivalent cluster vault role exists. Inspect instead of duplicating.')
            parameters = {'clusterPrincipalId':{'value':principal}}
        else:
            previous('cluster-role')
            if stage == 'deploy':
                validation = previous('validate')
                current = service_result('validate')
                if not service_passed(current) or validation['templateSha256'] != hashlib.sha256((ROOT / TEMPLATES['deploy']).read_bytes()).hexdigest(): raise RuntimeError('Positive current validation/configuration match required before Deploy')
            record['privateInputsReceipt'] = inspect_inputs(stage)
            metadata = az(['keyvault','secret','list','--subscription',SUB,'--vault-name','kv-lbox-weu-4766ea','--query','[].{name:name,enabled:attributes.enabled}'])
            if {row['name'] for row in metadata if row['enabled']} & set(SECRET_NAMES) != set(SECRET_NAMES): raise RuntimeError('Two required enabled credential secrets missing')
            parameters = {'deploymentMode':{'value':'Validate' if stage == 'validate' else 'Deploy'}}
        owned = {rid.lower() for rid in az(['resource','list','--subscription',SUB,'-g',RG,'--query','[].id'])} | {row['id'].lower() for row in R['assignments']()}
        args = ['--subscription',SUB,'-g',RG,'-n',action,'--template-file',str(ROOT / TEMPLATES[stage])]
        if parameters is not None: args += ['--parameters','@-']
        preview = az(['deployment','group','what-if',*args,'--result-format','FullResourcePayloads','--no-pretty-print'],parameters,timeout=300)
        record['previewChanges'] = check_preview(stage,preview,owned,principal)
        record['templateSha256'] = hashlib.sha256((ROOT / TEMPLATES[stage]).read_bytes()).hexdigest()
        if stage == 'secrets': parameters = normalise_lcm_parameters(L['secret_parameters']())
        record['status'] = 'apply-pending'; save()
        az(['deployment','group','create',*args,'--no-wait'],parameters,timeout=180); parameters = None
        record['status'] = 'submitted-observe-before-continuing'; save(); deadline = time.monotonic() + wait_seconds
        while True:
            result = az(['deployment','group','show','--subscription',SUB,'-g',RG,'-n',action,'--query','{id:id,state:properties.provisioningState,code:properties.error.code}'])
            record['deploymentId'] = result['id']; record['deploymentState'] = result['state']; record['deploymentErrorCode'] = result.get('code'); save()
            if result['state'] in ['Failed','Canceled']: raise RuntimeError('ARM/service stage failed. Preserve state, do not replay.')
            if result['state'] == 'Succeeded':
                if stage not in ['validate','deploy']: break
                service = service_result(stage); record['serviceResult'] = service; save()
                if service_passed(service): break
                if str(service['action'].get('status','')).lower() in ['error','failed','canceled']: raise RuntimeError('Service action failed despite ARM acceptance. Do not Deploy/replay Validate.')
            if time.monotonic() >= deadline: raise TimeoutError('Still submitted or reported service success unproven')
            time.sleep(20)
        if stage == 'secrets':
            metadata = az(['keyvault','secret','list','--subscription',SUB,'--vault-name','kv-lbox-weu-4766ea','--query','[].{name:name,id:id,enabled:attributes.enabled}'])
            if {row['name'] for row in metadata if row['enabled']} & set(SECRET_NAMES) != set(SECRET_NAMES): raise RuntimeError('Published two-secret metadata readback differs')
            record['secretMetadata'] = metadata
        elif stage == 'prerequisites':
            cluster = L['rest'](CLUSTER)
            record['clusterReadback'] = {'id':cluster['id'],'location':cluster['location'],'identity':cluster['identity'],'provisioningState':cluster['properties'].get('provisioningState')}
            record['edgeDevices'] = []
            for rid in sorted(effects(stage) - {CLUSTER.lower()}):
                edge = L['rest'](rid)
                if edge['id'].lower() != rid or edge.get('kind') != 'HCI' or edge.get('properties',{}).get('provisioningState') not in [None,'Succeeded']:
                    raise RuntimeError('Expected inspected HCI edge-device resource differs')
                record['edgeDevices'].append({'id':edge['id'],'kind':edge.get('kind'),'provisioningState':edge.get('properties',{}).get('provisioningState')})
        elif stage == 'cluster-role':
            selected = [row for row in R['assignments']() if row['principalId'] == principal and row['scope'].lower() == VAULT.lower() and row['roleDefinitionId'].endswith('/4633458b-17de-408a-b874-0445c86b69e6')]
            if len(selected) != 1 or selected[0]['principalType'] != 'ServicePrincipal': raise RuntimeError('Exact cluster-only vault role readback differs')
            record['clusterVaultRole'] = selected[0]
        record['vaultPublicAccessAfter'] = az(['keyvault','show','--subscription',SUB,'-n','kv-lbox-weu-4766ea','--query','properties.publicNetworkAccess'])
        if record['vaultPublicAccessAfter'] != 'Disabled': raise RuntimeError('Private vault boundary changed unexpectedly')
        record['status'] = 'complete'
    except (subprocess.TimeoutExpired,TimeoutError): record['status'] = 'uncertain-or-still-running-inspect-do-not-repeat'
    except (RuntimeError,ValueError,KeyError,OSError,subprocess.CalledProcessError) as error:
        record['status'] = 'failed-inspect-before-resume'; record['errorType'] = type(error).__name__
        if isinstance(error,RuntimeError): record['error'] = str(error)
    except KeyboardInterrupt: record['status'] = 'interrupted-inspect-do-not-repeat'
    parameters = None; record['finishedAtUtc'] = datetime.now(timezone.utc).isoformat(); save(); print(json.dumps(record,indent=2))
    return 0 if record['status'] == 'complete' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('stage',choices=list(TEMPLATES)); parser.add_argument('--wait-seconds',type=int,default=1200)
    parser.add_argument('--resume-unsubmitted-secrets',action='store_true')
    args = parser.parse_args()
    if not 60 <= args.wait_seconds <= 7200: parser.error('wait bound must be 60–7200 seconds')
    if args.resume_unsubmitted_secrets and args.stage != 'secrets': parser.error('the pre-submission reconciliation applies only to secrets')
    raise SystemExit(main(args.stage,args.wait_seconds,args.resume_unsubmitted_secrets))
