"""Six exact new phase controls plus narrow signature/return-context controls."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import build
import plan
from test_profile import fixture_contract,fixture_stage


class MocChecks(unittest.TestCase):
    def test_recorded_parameter_case_and_actual_getnode_scope(self):
        contract=fixture_contract();before=copy.deepcopy(contract)
        self.assertTrue(plan.moc_contract_preflight(contract))
        self.assertEqual(contract,before)
        command=contract['nodes']['LB-NODE02']['commands']['Remove-MocPhysicalNode']
        command['parameterSets'][0]['parameters'][0]['name']='NODENAME'
        contract['initialMembership']['commands']=copy.deepcopy(contract['nodes']['LB-NODE02']['commands'])
        self.assertTrue(plan.moc_contract_preflight(contract))
        getter=contract['nodes']['LB-NODE02']['commands']['Get-MocNode']
        getter['parameterSets'][0]['parameters']=[{'name':'name','type':'System.String','mandatory':False}]
        with self.assertRaises(ValueError):plan.moc_contract_preflight(contract)
        source=build.qualifier()
        self.assertIn("-location 'MocLocation' -timeoutSeconds 20",source)
        self.assertNotIn('Get-MocPhysicalNode',source)
        self.assertIn("$node -ceq 'LB-NODE02'",source)

    def test_initial_membership_requires_explicit_observed_identity_binding(self):
        contract=fixture_contract();identity=contract['membershipIdentity'];read=contract['initialMembership']
        read['records'][0]['fields'][0]['scalar']['value']='lb-node01'
        before=copy.deepcopy(read)
        self.assertEqual(plan.membership_names(read,identity),sorted(plan.ORDER));self.assertEqual(read,before)
        for bad in ('lb-node01.ad.localbox.test','native-guid-not-a-Windows-name'):
            broken=copy.deepcopy(read);broken['records'][0]['fields'][0]['scalar']['value']=bad
            with self.assertRaises(ValueError):plan.membership_names(broken,identity)
        del contract['membershipIdentity']
        with self.assertRaises(ValueError):plan.moc_contract_preflight(contract)

    def test_off_selected_cpu_memory_start_use_running_survivor(self):
        worker=build.render()[0]['profile-worker-template.ps1']
        line=next(line for line in worker.splitlines() if line.startswith('    $mocObserver = if'))
        checks=[]
        for key,row in plan.stages().items():
            if row['effect'] not in ('cpu','memory','guest-start'):continue
            self.assertEqual(row['beforeStates'][row['node']],'Off')
            checks.append("$entry=ConvertFrom-Json '"+json.dumps(row)+"'\n$before=@{states=(ConvertFrom-Json '"+json.dumps(row['beforeStates'])+"' -AsHashtable)}\n"+line+"\nif($mocObserver -ceq $entry.node -or $before.states[$mocObserver] -cne 'Running' -or $mocObserver -ceq 'LB-DC01'){throw 'Off selected guest used as MOC observer'}\n")
        self.assertEqual(len(checks),8)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'survivor-fixture.ps1';path.write_text("$ErrorActionPreference='Stop'\n"+''.join(checks))
            result=subprocess.run(['pwsh','-NoLogo','-NoProfile','-NonInteractive','-File',str(path)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_typed_lists_shape_private_capture_and_unknown_identity_fail_closed(self):
        helper=build.CANONICAL/'scripts/smal-rolling-profile-20261109/moc-contract.ps1'
        common=build.render()[0]['common-render-fragment.ps1']
        guards=common[common.index('function Assert-Compute('):common.index('function Read-ComputeGuestStatic')]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'getnode-shape-fixture.ps1'
            source="$ErrorActionPreference='Stop'\n"+guards+"\n$t=$null;$e=$null;$ast=[Management.Automation.Language.Parser]::ParseFile('"+str(helper)+"',[ref]$t,[ref]$e);if($e.Count){throw 'Parse failed'}\n"
            source+="foreach($f in $ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -cin @('Digest','SafeValue','Member','OuterItems','Items','RetainTypedJson','Project-ProfileMocRecord','Resolve-ProfileMocMembers','Assert-ProfileMocMembership')},$true)){. ([ScriptBlock]::Create($f.Extent.Text))}\n"
            source+="$privateRoot='"+d+"'\n"+r"""
$list=[Collections.Generic.List[object]]::new()
$list.Add([pscustomobject]@{name='lb-node01';id='actual-native-id';properties=[pscustomobject]@{location='MocLocation'};credentials='DO_NOT_EXPORT';unknownData='DO_NOT_EXPORT'})
$items=Items @{data=@(,$list)} 'nodes'
if($items.Count -ne 1 -or $items[0].id -cne 'actual-native-id'){throw 'Typed list lost or dictionary keys treated as nodes'}
$record=Project-ProfileMocRecord $items[0]
$projection=$record|ConvertTo-Json -Depth 20 -Compress
if($projection.Contains('DO_NOT_EXPORT') -or -not $projection.Contains('actual-native-id')){throw 'Unsafe or lossy management projection'}
$capture=RetainTypedJson 'fixture-data' @($items)
if($capture.status -cne 'retained-private-JSON' -or -not ([IO.File]::ReadAllText($capture.path)).Contains('DO_NOT_EXPORT')){throw 'Private raw JSON was not retained intact'}
$binding=[pscustomobject]@{semantics='WindowsComputerName';location='MocLocation';fieldPath=@('name');evidenceSha256=('d'*64)}
$resolved=Resolve-ProfileMocMembers @($record) $binding
if($resolved.members[0] -cne 'LB-NODE01' -or $resolved.nativeNames[0].nativeName -cne 'lb-node01'){throw 'Native name lost or unjustified identity mapping'}
$blocked=$false;try{$null=Resolve-ProfileMocMembers @($record) $null}catch{$blocked=$true};if(-not $blocked){throw 'Unreviewed identity field admitted'}
$bad=[pscustomobject]@{name='lb-node01.ad.localbox.test';id='native-id'};$blocked=$false
try{$null=Resolve-ProfileMocMembers @((Project-ProfileMocRecord $bad)) $binding}catch{$blocked=$true};if(-not $blocked){throw 'Unknown FQDN mapped automatically'}
foreach($data in @('LB-NODE01',@{nodes=@{name='LB-NODE01'}},@{nodes=@('LB-NODE01')})){
    $blocked=$false;try{$null=Items @{data=$data} 'nodes'}catch{$blocked=$true};if(-not $blocked){throw 'String/dictionary envelope enumerated as nodes'}
}
$blocked=$false;try{Assert-ProfileMocMembership @{qualified=$false;membershipObserved=$false} @('LB-NODE01') $null}catch{$blocked=$true};if(-not $blocked){throw 'Unknown membership admitted CUD'}
"""
            path.write_text(source)
            result=subprocess.run(['pwsh','-NoLogo','-NoProfile','-NonInteractive','-File',str(path)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_required_extra_parameter_and_unknown_binding_refuse(self):
        for change in ('extra','missing','alias','module','ambiguous'):
            contract=fixture_contract();command=contract['nodes']['LB-NODE02']['commands']['Remove-MocPhysicalNode']
            if change=='extra':command['parameterSets'][0]['parameters'].append({'name':'UnknownRequired','type':'System.String','mandatory':True})
            elif change=='missing':command['parameterSets'][0]['parameters']=[]
            elif change=='alias':command['commandType']='Alias'
            elif change=='module':command['moduleName']=''
            else:command['parameterSets'].append(copy.deepcopy(command['parameterSets'][0]))
            with self.assertRaises(ValueError):plan.moc_contract_preflight(contract)

    def test_return_context_does_not_require_current_eight_devices_in_maintenance(self):
        for effect in ('resume','moc-add'):
            p,proof,now=fixture_stage(effect+'-LB-NODE02');proof['selectedEightDeviceMaintenanceVerified']=False
            self.assertTrue(plan.execution_preflight(p,effect+'-LB-NODE02',proof,now)['localEffectPrerequisitesAccepted'])
            proof['selectedMaintenanceContextVerified']=False
            with self.assertRaises(ValueError):plan.execution_preflight(p,effect+'-LB-NODE02',proof,now)

    def test_prior_effect_settlement_and_exact_moc_membership_are_required(self):
        for key in ('previousEffectIndependentlySettled','mocContractQualified','mocMembers','selectedNodeUpObserved'):
            p,proof,now=fixture_stage('moc-add-LB-NODE02')
            proof[key]=[] if key=='mocMembers' else False
            with self.assertRaises(ValueError):plan.execution_preflight(p,'moc-add-LB-NODE02',proof,now)

    def test_qualifier_is_parse_only_get_source_and_deadline_is_unsealed(self):
        source=build.qualifier()
        self.assertIn('Read-ProfileMoc $node',source)
        self.assertNotIn('& $command[0] -NodeName',source)
        self.assertNotIn('function Read-ComputeSnapshot',source)
        self.assertIsNone(plan.candidate()['executionApproval']['expiresAt'])
        self.assertFalse(plan.candidate()['executionApproval']['parentGo'])
        p,proof,now=fixture_stage('drain-LB-NODE02');p['executionApproval']['expiresAt']='2026-11-10T15:21:00+02:00'
        with self.assertRaises(ValueError):plan.execution_preflight(p,'drain-LB-NODE02',proof,now)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'qualifier.ps1';path.write_text(source)
            command="$t=$null;$e=$null;[Management.Automation.Language.Parser]::ParseFile('"+str(path)+"',[ref]$t,[ref]$e)|Out-Null;if($e.Count){$e|Out-String;exit 1}"
            result=subprocess.run(['pwsh','-NoLogo','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


def phase_control(node,effect):
    def test(self):
        key=effect+'-'+node;rows=plan.stages();names=list(rows);row=rows[key];index=names.index(key)
        self.assertEqual(names[index-1],('drain' if effect=='moc-remove' else 'resume')+'-'+node)
        self.assertEqual(row['beforeMocMembers'],sorted(plan.ORDER) if effect=='moc-remove' else sorted(n for n in plan.ORDER if n!=node))
        self.assertEqual(row['afterMocMembers'],sorted(n for n in plan.ORDER if n!=node) if effect=='moc-remove' else sorted(plan.ORDER))
        if effect=='moc-remove':self.assertEqual(names[index+1],'guest-stop-'+node)
        p,proof,now=fixture_stage(key);self.assertTrue(plan.execution_preflight(p,key,proof,now)['localEffectPrerequisitesAccepted'])
        wrong=copy.deepcopy(proof);wrong['mocMembers']=row['afterMocMembers']
        with self.assertRaises(ValueError):plan.execution_preflight(p,key,wrong,now)
        # Execute only the exact extracted MOC branch. Native-named mutations are
        # an in-memory fixture module changing a synthetic membership array.
        files,_=build.render();worker=files['profile-worker-template.ps1'];common=files['common-render-fragment.ps1']
        start=worker.index("            { $_ -cin @('moc-remove','moc-add') } {")
        end=worker.index("            'guest-start' {",start)
        branch=worker[start:end];body=branch[branch.index('{\n')+2:branch.rfind('}')]
        guards=common[common.index('function Assert-Compute('):common.index('function Read-ComputeGuestStatic')]
        helper=(build.CANONICAL/'scripts/smal-rolling-profile-20261109/moc-contract.ps1').read_text()
        pure=helper[helper.index('function Assert-ProfileMocMembership'):]
        for fail_readback in (False,True):
            setup="$ErrorActionPreference='Stop'\n"+guards+pure+'\n'
            setup+="$plan=ConvertFrom-Json '"+json.dumps(p)+"'\n$entry=ConvertFrom-Json '"+json.dumps(row)+"'\n"
            setup+="$global:Members=ConvertFrom-Json '"+json.dumps(row['beforeMocMembers'])+"'\n$global:Calls=0;$global:Events=@();$global:Wrong=$"+str(fail_readback).lower()+"\n"
            setup+="""
$module=New-Module -Name Moc -ScriptBlock {
    function Remove-MocPhysicalNode { param([string]$NodeName) $global:Calls++;$global:Members=@($global:Members|Where-Object {$_ -cne $NodeName}) }
    function New-MocPhysicalNode { param([string]$NodeName) $global:Calls++;$global:Members=@($global:Members+$NodeName|Sort-Object) }
    Export-ModuleMember -Function Remove-MocPhysicalNode,New-MocPhysicalNode
}
Import-Module $module
$global:FixtureCommands=$plan.mocContract.nodes.PSObject.Properties[$entry.node].Value.commands
$ProfileMocRead={param($node) @{qualified=$true;membershipObserved=$true;commands=@{'Get-MocNode'=@{contractSha256=('c'*64)};'Remove-MocPhysicalNode'=@{contractSha256=('c'*64)};'New-MocPhysicalNode'=@{contractSha256=('c'*64)}};members=@($global:Members)}}
function Invoke-Command { param($Session,$ArgumentList,$ErrorAction,$ScriptBlock) & $ScriptBlock @ArgumentList }
function Read-ProfileMoc { param($node) @{qualified=$true;observerNode=$node;commands=$global:FixtureCommands;members=$(if($global:Wrong){@($entry.beforeMocMembers)}else{@($global:Members)})} }
function Save-R2Worker { param($phase) $global:Events+=@{phase=$phase;rpcReturned=$state.rpcReturned;outcome=$state.outcome} }
$session='inert';$state=@{rpcInvoked=$true;outcome='unknown'};$failure=$null
try {
"""+body+"\n}catch{$failure=$_.Exception.Message}\n@{failure=$failure;calls=$global:Calls;events=$global:Events;state=$state;members=@($global:Members)}|ConvertTo-Json -Depth 30 -Compress\n"
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)/'moc-phase-fixture.ps1';path.write_text(setup)
                result=subprocess.run(['pwsh','-NoLogo','-NoProfile','-NonInteractive','-File',str(path)],capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                report=json.loads(result.stdout)
                self.assertEqual(report['calls'],1)
                self.assertTrue(report['state']['rpcReturned'])
                self.assertEqual(report['events'][0]['phase'],'rpc-returned')
                self.assertEqual(report['events'][0]['outcome'],'rpc-returned-await-independent-observation')
                self.assertNotEqual(report['state']['outcome'],'settled')
                self.assertEqual(report['members'],row['afterMocMembers'])
                if fail_readback:
                    self.assertIn('Actual MOC membership differs',report['failure'])
                    self.assertFalse(report['state']['postReadSucceeded'])
                else:
                    self.assertIsNone(report['failure'])
                    self.assertTrue(report['state']['postReadSucceeded'])
    return test


for _node in plan.ORDER:
    for _effect in ('moc-remove','moc-add'):
        setattr(MocChecks,'test_'+_effect.replace('-','_')+'_'+_node.replace('-','_'),phase_control(_node,_effect))
