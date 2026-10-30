"""Read-only cloud acceptance evidence after a positively completed service Deploy.

No kubeconfig, credential value, raw service exception or signed URI is retained.
Collects facts only. Windows storage/recovery acceptance remains separate.
"""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import runpy
import re

ROOT = Path(__file__).resolve().parents[1]
D = runpy.run_path(str(ROOT / 'scripts/deploy-smal-three-node-cluster.py'),run_name='three_node_cloud_acceptance')
P, az, OUT, SUB, RG = (D[key] for key in ['P','az','OUT','SUB','RG'])


def get_projection(rid,version,query):
    return az(['rest','--method','get','--url','https://management.azure.com' + rid + '?api-version=' + version,'--query',query])


def audit_metadata(data):
    rows = data.get('value') if isinstance(data,dict) else data
    if not isinstance(rows,list): raise RuntimeError('Unexpected vault diagnostic-settings response shape')
    return [{'name':row.get('name'),'storageAccountId':row.get('storageAccountId'),'logs':row.get('logs')} for row in rows]


def main(receipt='three-node-cloud-acceptance-observation.json'):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,95}\.json',receipt): raise RuntimeError('Invalid read-only observation receipt name')
    D['A']['source_guard'](['scripts/inspect-smal-three-node-cloud-health.py','scripts/deploy-smal-three-node-cluster.py',
        'docs/deployment-2026-10-29/three-node-cluster-deploy-observation-follow-up-20261030.json'])
    completed = D['previous']('deploy')
    if not D['service_passed'](completed.get('serviceResult',{})): raise RuntimeError('Positive service Deploy success required before final acceptance inspection')
    path = OUT / receipt
    record = {'beganAtUtc':datetime.now(timezone.utc).isoformat(),'status':'pending-read-only','platformReadinessVerified':False,'azureMutationPerformed':False}
    with path.open('x') as stream: stream.write(json.dumps(record,indent=2) + '\n')
    try:
        record['arcMachines'] = P['cloud_nodes'](); P['verify_cloud'](record['arcMachines'])
        record['cluster'] = get_projection(D['CLUSTER'],D['API'],'{id:id,name:name,location:location,identity:identity,provisioningState:properties.provisioningState,status:properties.status,cloudId:properties.cloudId,lastSync:properties.lastSyncTimestamp}')
        record['serviceDeploy'] = D['service_result']('deploy')
        if not D['service_passed'](record['serviceDeploy']): raise RuntimeError('Current reported deployment outcome no longer positively succeeds')
        resources = az(['resource','list','--subscription',SUB,'-g',RG,'--query','[].{id:id,name:name,type:type,location:location}'])
        record['resources'] = resources
        bridges = [row for row in resources if row['type'].lower() == 'microsoft.resourceconnector/appliances']
        locations = [row for row in resources if row['type'].lower() == 'microsoft.extendedlocation/customlocations' and row['name'] == 'cl-localbox-smal-weu-1']
        record['bridgeResources'] = [get_projection(row['id'],'2022-10-27','{id:id,name:name,location:location,provisioningState:properties.provisioningState,status:properties.status,distribution:properties.distribution}') for row in bridges]
        record['customLocationResources'] = [get_projection(row['id'],'2021-08-15','{id:id,name:name,location:location,provisioningState:properties.provisioningState,hostResourceId:properties.hostResourceId,namespace:properties.namespace}') for row in locations]
        record['vault'] = az(['keyvault','show','--subscription',SUB,'-n','kv-lbox-weu-4766ea','--query','{id:id,pna:properties.publicNetworkAccess,rbac:properties.enableRbacAuthorization,purgeProtection:properties.enablePurgeProtection,softDeleteDays:properties.softDeleteRetentionInDays}'])
        audit = az(['monitor','diagnostic-settings','list','--subscription',SUB,'--resource',D['VAULT']])
        record['vaultAudit'] = audit_metadata(audit)
        record['storage'] = [az(['storage','account','show','--subscription',SUB,'-g',RG,'-n',name,'--query','{id:id,name:name,pna:publicNetworkAccess,sharedKey:allowSharedKeyAccess,sku:sku.name}']) for name in ['stlboxdiagweu4766ea','stlboxwitweu4766ea']]
        record['defender'] = az(['security','pricing','show','--subscription',SUB,'--name','VirtualMachines','--query','{tier:pricingTier,subPlan:subPlan,freeTrialRemaining:freeTrialRemainingTime}'])
        record['status'] = 'observed-cloud-state-requires-storage-recovery-and-owner-acceptance'
    except (RuntimeError,ValueError,KeyError,OSError) as error:
        record['status'] = 'failed-read-only-observation'; record['errorType'] = type(error).__name__
        if isinstance(error,RuntimeError): record['error'] = str(error)
    record['finishedAtUtc'] = datetime.now(timezone.utc).isoformat(); path.write_text(json.dumps(record,indent=2) + '\n')
    print(json.dumps(record,indent=2))
    return 0 if record['status'].startswith('observed-') else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--receipt',default='three-node-cloud-acceptance-observation.json'); args = parser.parse_args()
    raise SystemExit(main(args.receipt))
