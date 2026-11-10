import copy
import hashlib
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import build
import plan


def fixture_contract():
    commands={}
    for name in plan.MOC_COMMANDS:
        commands[name]={'name':name,'commandType':'Function','moduleName':'FixtureMoc','moduleVersion':'1.0','modulePath':'fixture-only',
            'moduleSha256':'a'*64,'definitionSha256':'b'*64,'contractSha256':'c'*64,
            'parameterSets':[{'name':'fixture','parameters':[] if name=='Get-MocPhysicalNode' else [{'name':'NodeName','type':'System.String','mandatory':True}]}]}
    return {'nodes':{node:{'qualified':True,'observerNode':node,'commands':copy.deepcopy(commands),'membershipObserved':True,'members':sorted(plan.ORDER)} for node in plan.ORDER}}


def fixture_stage(stage):
    now=datetime(2026,11,10,10,10,tzinfo=timezone.utc)
    p=plan.candidate();p['baseline']={'sealed':True};p['admission']={'sealed':True};p['mocContract']=fixture_contract()
    p['transitionContract']['deviceOwners']={str(i):plan.ORDER[i//8] for i in range(24)}
    p['executionApproval']={'parentGo':True,'originalOperationsReconciled':True,'expiresAt':(now+timedelta(minutes=10)).isoformat()}
    row=p['transitionContract']['stages'][stage]
    proof={'originalOperationsReconciled':True,'retainedRootsAbsent':True,'exactSourcePublished':True,'localWindowsAuthorityVerified':True,
        'exactStorageIdentities':True,'volumeGrowthBudgetsFit':True,'supportedProfilesVerified':True,'allHealthyNoJobs':True,
        'selectedEightDeviceMaintenanceVerified':True,'selectedMaintenanceContextVerified':True,'twoHealthySurvivors':True,
        'infrastructureMigrationAdmitted':True,'mocContractQualified':True,'mocMembers':row['beforeMocMembers'],
        'selectedNodeUpObserved':True,'previousStage':row['previousStage'],'previousEffectIndependentlySettled':True,
        'beforeProfiles':row['beforeProfiles'],'beforeStates':row['beforeStates'],'observedAt':now.isoformat(),
        'outerMemoryBytes':549750304768,'physicalFreeBytes':300*plan.GIB}
    return p,proof,now


class ProfileChecks(unittest.TestCase):
    def test_exact_order_and_no_node01_memory_write(self):
        rows=plan.stages();self.assertEqual(len(rows),25)
        self.assertEqual(next(iter(rows)),'drain-LB-NODE02')
        self.assertNotIn('memory-LB-NODE01',rows)
        self.assertEqual(rows['complete']['beforeProfiles']['LB-NODE02']['cpu'],20)
        self.assertEqual(rows['complete']['beforeProfiles']['LB-NODE01']['memory'],64*plan.GIB)

    def test_setting_support_not_blocked_by_cim_formatting(self):
        for node in plan.ORDER:
            observed={'id':plan.IDS[node],'generation':2,'version':'12.0','nested':True,'dynamicMemory':False,'maxCpuPerNuma':32,'minimumMemoryBytes':536870912,'maximumMemoryBytes':1099511627776,'outerNumaSpanning':True}
            result=plan.setting_preflight(node,observed)
            self.assertTrue(result['settingsSupportedByObservedBounds']);self.assertFalse(result['cimFormattingIsSupportGate'])
            observed['maxCpuPerNuma']=8
            with self.assertRaises(ValueError):plan.setting_preflight(node,observed)

    def test_unsealed_candidate_cannot_execute(self):
        with self.assertRaises(ValueError):plan.execution_preflight(plan.candidate(),'drain-LB-NODE02',{})

    def test_runtime_health_original_state_and_permission_gates(self):
        p,proof,now=fixture_stage('drain-LB-NODE02')
        self.assertTrue(plan.execution_preflight(p,'drain-LB-NODE02',proof,now)['transportAuthoritySeparate'])
        for key in ('originalOperationsReconciled','localWindowsAuthorityVerified','allHealthyNoJobs','volumeGrowthBudgetsFit'):
            q=copy.deepcopy(proof);q[key]=False
            with self.assertRaises(ValueError):plan.execution_preflight(p,'drain-LB-NODE02',q,now)

    def test_templates_preserve_protected_helper_and_reconciliation(self):
        files,pins=build.render()
        self.assertIn('New-ComputeSession',files['profile-worker-template.ps1'])
        self.assertIn('sourceSha256',files['profile-stage-template.ps1'])
        self.assertIn('Unresolved launch intent',files['profile-stage-template.ps1'])
        self.assertNotIn("'cluster-stop' {",files['profile-worker-template.ps1'])
        self.assertNotIn("'startup-grant' {",files['profile-worker-template.ps1'])
        self.assertIn('profile operation is not closed',files['proposed-canonical-startup.ps1'])

    def test_capsule_parse_and_unsealed_fail_before_action(self):
        data=build.capsule(plan.candidate(),'drain-LB-NODE02')
        with tempfile.TemporaryDirectory() as d:
            for name in ('worker','dispatcher'):
                path=Path(d)/(name+'.ps1');path.write_text(data[name])
                command="$t=$null;$e=$null;[Management.Automation.Language.Parser]::ParseFile('"+str(path)+"',[ref]$t,[ref]$e)|Out-Null;if($e.Count){exit 1}"
                r=subprocess.run(['pwsh','-NoLogo','-NoProfile','-NonInteractive','-Command',command],capture_output=True,timeout=30);self.assertEqual(r.returncode,0)
                r=subprocess.run(['pwsh','-NoLogo','-NoProfile','-NonInteractive','-File',str(path)],capture_output=True,timeout=30)
                self.assertNotEqual(r.returncode,0)
                self.assertIn(b'Unsealed profile',r.stderr)

    def test_capsule_rejects_source_injection_and_wrong_targets(self):
        with self.assertRaises(ValueError):build.capsule(plan.candidate(),'drain-LB-NODE02',"x';Start-VM bad")
        p=plan.candidate();p['transitionContract']['stages']['cpu-LB-NODE02']['targetCpu']=32
        with self.assertRaises(ValueError):build.capsule(p,'cpu-LB-NODE02')
        original=plan.candidate();original['executionApproval']={'parentGo':True,'expiresAt':'2026-01-01T00:00:00+00:00'}
        observation=build.capsule(original,'cpu-LB-NODE02','a'*40,mode='observe')
        self.assertIn("$mode='observe'",observation['dispatcher'])
        with self.assertRaises((ValueError,KeyError)):build.capsule(original,'cpu-LB-NODE02','a'*40,mode='dispatch')

    def test_exact_proposed_delta_rendered_hashes(self):
        files,_=build.render()
        self.assertEqual({name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()},build.RENDER_PINS)

    def test_startup_install_does_not_change_original_capsule(self):
        files,pins=build.render()
        before=build.capsule(plan.candidate(),'drain-LB-NODE02')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in pins:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes((build.CANONICAL/name).read_bytes())
            (root/'scripts/start-smal-existing-guests.ps1').write_text(files['proposed-canonical-startup.ps1'])
            with patch.object(build,'CANONICAL',root):
                self.assertEqual(build.render()[0],files)
                after=build.capsule(plan.candidate(),'drain-LB-NODE02',mode='observe')
                self.assertEqual(after['worker'],before['worker'])
                self.assertEqual(after['planSha256'],before['planSha256'])

    def test_changed_canonical_dependency_is_not_silently_rendered(self):
        _,pins=build.render()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in pins:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes((build.CANONICAL/name).read_bytes())
            for name in pins:
                path=root/name;original=path.read_bytes();path.write_bytes(original+b'\n# changed\n')
                with patch.object(build,'CANONICAL',root),self.assertRaisesRegex(ValueError,'Canonical input differs'):
                    build.render()
                path.write_bytes(original)


if __name__=='__main__':unittest.main()
