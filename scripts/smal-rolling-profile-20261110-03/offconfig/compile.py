"""Private limited03 source compiler. No native/Git calls and no changes to sealed plan/source."""
import base64
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import sys
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
OLD=Path('/tmp/opencode/smal-rolling03-next-stage-20261110/advance03.py')
assert hashlib.sha256(OLD.read_bytes()).hexdigest()=='7921b6c43618369cf8bc4e948773addc2b2ff0af69961baa0c84643d9d804fba'
spec=importlib.util.spec_from_file_location('_original03_advance',OLD);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
PLAN_SHA=old.PLAN_SHA
sha=old.sha

def common():
 old.verify_source_pins();v=old.load_plan();raw=(R/'reference/plan.json').read_bytes();assert sha(raw)==PLAN_SHA
 decision=Path('/tmp/opencode/smal-rolling-execution-20261110-03/offconfig-parent-qualification.json').read_bytes()
 assert sha(decision)=='0ec7150bd3d1bba859bce60eb2ac0a2d06a2c3964311e390b722eb6181c3ec54'
 policy=json.loads(decision);assert policy['planSha256']==PLAN_SHA and policy['stages']==['cpu-LB-NODE02','memory-LB-NODE02','guest-start-LB-NODE02'] and policy['nativeGoIssued'] is False
 unresolved=(R/'unresolved-storage-identities.json').read_text();rows=json.loads(unresolved);assert len(rows)==8 and len({x['UniqueId'] for x in rows})==8
 functions=old.build.render()['common.ps1']
 functions+='\n'+(R/'offconfig-membership-v02.ps1').read_text()
 functions+='\n'+(R/'offconfig-nodes-v03.ps1').read_text()
 functions+='\n'+(R/'offconfig-v03.ps1.in').read_text().replace('@@UNRESOLVED_JSON@@',json.dumps(rows,separators=(',',':')))
 return v,functions

def observer(stage='cpu-LB-NODE02'):
 v,functions=common();assert stage in ('cpu-LB-NODE02','memory-LB-NODE02','guest-start-LB-NODE02')
 raw=old.canonical(v)
 prefix="$ErrorActionPreference='Stop'\n$ComputeCapacityLibraryOnly=$true\n$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+base64.b64encode(raw).decode()+"'))|ConvertFrom-Json)\n$planSha='"+PLAN_SHA+"'\n$stage='"+stage+"'\n"
 labels=sorted(set(re.findall(r"'(OFFCONFIG:[^'\r\n]*)'",functions)))
 tail="\nif($env:COMPUTERNAME -cne 'LocalBox-Client'){throw 'OFFCONFIG: wrong qualification host'}\n$script:OffconfigNodeStateFieldTypes=$null\n$staticLabels=ConvertFrom-Json '"+json.dumps(labels)+"'\ntry{\n $evidence=Read-OffconfigEvidence $stage\n $result=@{status='complete-limited-offconfig-GET';mutationPerformed=$false;operationId=$plan.operationId;planSha256=$planSha;requestedStage=$stage;qualificationSourceSha256='"+sha(functions.encode())+"';currentOfflineOwnerProven=$false;exactStorageIdentities=$false;evidence=$evidence;nodeStateFieldTypes=$script:OffconfigNodeStateFieldTypes;atUtc=[datetime]::UtcNow.ToString('o')}\n}catch{\n $errorRecord=$_;$label=$null\n foreach($known in $staticLabels){if($errorRecord.Exception.Message -ceq $known -or $errorRecord.Exception.Message.StartsWith($known+'.',[StringComparison]::Ordinal) -or $errorRecord.Exception.Message.StartsWith($known+'[',[StringComparison]::Ordinal)){$label=$known;break}}\n $result=@{status='failed-limited-offconfig-GET';mutationPerformed=$false;operationId=$plan.operationId;planSha256=$planSha;requestedStage=$stage;qualificationSourceSha256='"+sha(functions.encode())+"';currentOfflineOwnerProven=$false;exactStorageIdentities=$false;evidence=$null;guardLabel=$label;exceptionType=$errorRecord.Exception.GetType().FullName;stackLines=@([regex]::Matches([string]$errorRecord.ScriptStackTrace,'line (\\d+)')|Select-Object -First 12|ForEach-Object {[int]$_.Groups[1].Value});nodeStateFieldTypes=$script:OffconfigNodeStateFieldTypes;rawMessageSuppressed=$true;atUtc=[datetime]::UtcNow.ToString('o')}\n}\n$result|ConvertTo-Json -Depth 60 -Compress\n"
 return prefix+functions+tail

if __name__=='__main__':
 text=observer();path=R/'read-smal-rolling03-offconfig-cpu-qualification-20261110-03.ps1';path.write_text(text)
 print(json.dumps({'source':str(path),'sha256':sha(text.encode()),'bytes':len(text.encode()),'nativeExecuted':False,'stage':'cpu-LB-NODE02'},indent=2))
