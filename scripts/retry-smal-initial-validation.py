"""One state-guarded initial-validation retry after exact LCM username correction.

Never applies to DeploymentFailed or active tasks. Updates only the existing
deploymentSettings resource via its documented CreateOrUpdate operation. Does not
reapply cluster, edges, identities, roles, secrets, licences or storage.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
REC = runpy.run_path(str(ROOT / 'scripts/smal-validation-recovery.py'),run_name='initial_validation_retry_guard')
D = REC['D']; OUT = D['OUT']; ACTION = 'localbox-three-node-validate-lcm-format-20261029'


def validate_retry_preview(preview,owned):
    if preview.get('status') != 'Succeeded': raise RuntimeError('Corrected validation preview failed')
    seen = []
    for row in preview.get('changes',[]):
        rid = row.get('resourceId','').lower(); kind = row.get('changeType')
        if rid == D['SETTINGS'].lower():
            if kind not in ['NoChange','Modify']: raise RuntimeError('Retry must update the existing settings, never create/delete them')
            before = row.get('before',{}).get('properties',{}); after = row.get('after',{}).get('properties',{})
            for key in ['deploymentMode','arcNodeResourceIds','deploymentConfiguration']:
                previous = before.get(key); desired = after.get(key)
                if key == 'arcNodeResourceIds': previous,desired = ({str(rid).lower() for rid in previous or []},{str(rid).lower() for rid in desired or []})
                if previous != desired: raise RuntimeError('Configuration changed beyond the external LCM encoding correction')
            if after.get('deploymentMode') != 'Validate': raise RuntimeError('Retry may not start deployment')
            seen.append({'id':row['resourceId'],'changeType':kind})
        elif kind not in ['Ignore','NoChange'] or rid not in owned or row.get('before') != row.get('after'):
            raise RuntimeError('Unlisted resource effect in initial validation retry')
    if len(seen) != 1: raise RuntimeError('Exactly the existing deployment-settings resource must be previewed')
    return seen


def main(wait_seconds=1800):
    head = D['A']['source_guard'](['scripts/retry-smal-initial-validation.py','scripts/smal-validation-recovery.py','scripts/deploy-smal-three-node-cluster.py',
        'infra/arm/localbox-three-node-settings.json','docs/deployment-2026-10-29/three-node-cluster-validate-receipt.json',
        'docs/deployment-2026-10-29/lcm-credential-format-correction-receipt.json'])
    path = OUT / 'three-node-cluster-validate-after-lcm-format-fix-receipt.json'
    record = {'beganAtUtc':datetime.now(timezone.utc).isoformat(),'sourceCommit':head,'status':'pending','stage':'validate',
              'deploymentName':ACTION,'initialValidationOnly':True,'deploySubmitted':False,'clusterReapplied':False,'rolesOrSecretsReapplied':False,'platformReadinessVerified':False}
    with path.open('x') as stream: stream.write(json.dumps(record,indent=2) + '\n')
    def save(): path.write_text(json.dumps(record,indent=2) + '\n')
    try:
        D['preflight'](); record['terminalInitialValidationProof'] = REC['current_failure']()
        original_path = OUT / 'three-node-cluster-validate-receipt.json'; original = json.loads(original_path.read_text())
        current_hash = hashlib.sha256((ROOT / D['TEMPLATES']['validate']).read_bytes()).hexdigest()
        if original.get('stage') != 'validate' or original.get('deploymentState') != 'Failed' or original.get('templateSha256') != current_hash: raise RuntimeError('Original failed validation/settings hash does not match exactly')
        fix = json.loads((OUT / 'lcm-credential-format-correction-receipt.json').read_text())
        if fix.get('status') != 'complete-one-lcm-username-format-version-only' or fix.get('unqualifiedCredentialReadbackMatched') is not True or fix.get('passwordRotated') is not False: raise RuntimeError('Exact successful username-only secret correction proof missing')
        current_secret = D['az'](['keyvault','secret','show','--subscription',D['SUB'],'--vault-name','kv-lbox-weu-4766ea','--name',D['NAME'] + '-AzureStackLCMUserCredential','--query','{id:id,enabled:attributes.enabled}'])
        if current_secret != {'id':fix['newVersionId'],'enabled':True}: raise RuntimeError('Corrected LCM secret latest metadata differs')
        if D['az'](['deployment','group','list','--subscription',D['SUB'],'-g',D['RG'],'--query',"[?name=='" + ACTION + "'].name"]): raise RuntimeError('Retry deployment identity already exists. Inspect, never repeat.')
        record['privateInputsReceipt'] = D['inspect_inputs']('validate-lcm-format-fix')
        record['originalFailedReceiptSha256'] = hashlib.sha256(original_path.read_bytes()).hexdigest(); record['templateSha256'] = current_hash
        record['correctedLcmVersionId'] = fix['newVersionId']
        owned = {rid.lower() for rid in D['az'](['resource','list','--subscription',D['SUB'],'-g',D['RG'],'--query','[].id'])} | {row['id'].lower() for row in D['R']['assignments']()}
        args = ['--subscription',D['SUB'],'-g',D['RG'],'-n',ACTION,'--template-file',str(ROOT / D['TEMPLATES']['validate']),'--parameters','@-']
        parameters = {'deploymentMode':{'value':'Validate'}}
        preview = D['az'](['deployment','group','what-if',*args,'--result-format','FullResourcePayloads','--no-pretty-print'],parameters,timeout=300)
        record['previewChanges'] = validate_retry_preview(preview,owned)
        # Recheck terminal/non-deployment state immediately before the single PUT.
        REC['current_failure']()
        record['status'] = 'existing-settings-validation-retry-pending'; save()
        D['az'](['deployment','group','create',*args,'--no-wait'],parameters,timeout=180)
        record['status'] = 'submitted-observe-before-deploy'; save(); deadline = time.monotonic() + wait_seconds
        while True:
            arm = D['az'](['deployment','group','show','--subscription',D['SUB'],'-g',D['RG'],'-n',ACTION,'--query','{id:id,state:properties.provisioningState,code:properties.error.code}'])
            record['deploymentId'] = arm['id']; record['deploymentState'] = arm['state']; record['deploymentErrorCode'] = arm.get('code'); save()
            if arm['state'] in ['Failed','Canceled']: raise RuntimeError('Corrected initial validation failed. Preserve this attempt; no automatic retry or Deploy.')
            if arm['state'] == 'Succeeded':
                result = D['service_result']('validate'); record['serviceResult'] = result; save()
                if D['service_passed'](result): break
                if str(result['action'].get('status','')).lower() in ['error','failed','canceled']: raise RuntimeError('Reported service validation did not pass')
            if time.monotonic() >= deadline: raise TimeoutError('Still pending or positive service success unproven')
            time.sleep(20)
        record['status'] = 'complete'
    except (TimeoutError,subprocess.TimeoutExpired): record['status'] = 'uncertain-or-still-running-inspect-do-not-repeat'
    except (RuntimeError,ValueError,KeyError,OSError) as error:
        record['status'] = 'failed-inspect-before-resume'; record['errorType'] = type(error).__name__
        if isinstance(error,RuntimeError): record['error'] = str(error)
    record['finishedAtUtc'] = datetime.now(timezone.utc).isoformat(); save(); print(json.dumps(record,indent=2))
    return 0 if record['status'] == 'complete' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--wait-seconds',type=int,default=1800); args = parser.parse_args()
    if not 60 <= args.wait_seconds <= 7200: parser.error('wait bound must be 60–7200 seconds')
    raise SystemExit(main(args.wait_seconds))
