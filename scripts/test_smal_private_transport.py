"""Focused byte transport and fixed cleanup guard tests. No network/native lab calls."""
import ast
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'scripts/smal-private-powershell.py'
nodes=ast.parse(SOURCE.read_bytes())
NAMES={'ssh_args','run_ssh','stdin_loader'}
H={'base64':base64,'hashlib':hashlib,'subprocess':subprocess,'H':{'KEY':Path('fixture-key'),'KNOWN':Path('fixture-known'),'ALIAS':'fixture-alias'}}
exec(compile(ast.Module(body=[n for n in nodes.body if isinstance(n,ast.FunctionDef) and n.name in NAMES],type_ignores=[]),str(SOURCE),'exec'),H)


class TransportChecks(unittest.TestCase):
    def test_large_source_is_binary_and_short_source_retains_devnull(self):
        for streaming in (False,True):
            data=('é\n'+'# x'*120000).encode();result=subprocess.CompletedProcess(['fixture'],0,b'{"ok":true}\r\n',b'fixture')
            with patch.object(subprocess,'run',return_value=result) as run:
                value=H['run_ssh'](['fixture'],data,streaming,90)
            kwargs=run.call_args.kwargs
            self.assertNotIn('text',kwargs);self.assertNotIn('encoding',kwargs)
            if streaming:self.assertIs(kwargs['input'],data)
            else:self.assertEqual(kwargs['stdin'],subprocess.DEVNULL)
            self.assertEqual(value.stdout,'{"ok":true}\r\n')

    def test_security_args_and_short_encoded_path_are_preserved(self):
        payload=base64.b64encode('inert'.encode('utf-16-le')).decode()
        short=H['ssh_args'](12345,'fixture',payload,False);large=H['ssh_args'](12345,'fixture',payload,True)
        self.assertIn('-n',short);self.assertNotIn('-n',large)
        for flag in ('StrictHostKeyChecking=yes','IdentitiesOnly=yes','IdentityAgent=none','BatchMode=yes','PasswordAuthentication=no','ForwardAgent=no','ClearAllForwardings=yes'):
            self.assertIn(flag,short);self.assertIn(flag,large)
        self.assertTrue(short[-1].startswith('powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand '))
        self.assertNotIn('powershell.exe',large[-1]);self.assertIn('[ScriptBlock]::Create',large[-1])
        with self.assertRaises(Exception):H['ssh_args'](12345,'fixture',"bad' payload",True)

    def test_exact_359kb_direct_default_shell_roundtrip(self):
        body=b"@{status='inert';value='unicode-"+'é'.encode()+b"'}|ConvertTo-Json -Compress\n#"
        data=body+b'x'*(358958-len(body))
        loader=H['stdin_loader'](data);remote=H['ssh_args'](12345,'fixture',loader,True)[-1]
        result=H['run_ssh'](['pwsh','-NoLogo','-NoProfile','-NonInteractive','-Command',remote],data,True,30)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['value'],'unicode-é')
        for bad in (data[:-1],data[:-1]+b'y'):
            result=H['run_ssh'](['pwsh','-NoLogo','-NoProfile','-NonInteractive','-Command',remote],bad,True,30)
            self.assertNotEqual(result.returncode,0);self.assertIn('ReviewedSourceFailure:',result.stderr)

    def test_source_error_stays_sanitised(self):
        data=b"throw 'DO_NOT_EXPORT_THIS_ERROR'\n";remote=H['ssh_args'](12345,'fixture',H['stdin_loader'](data),True)[-1]
        result=H['run_ssh'](['pwsh','-NoLogo','-NoProfile','-NonInteractive','-Command',remote],data,True,30)
        self.assertNotEqual(result.returncode,0);self.assertIn('ReviewedSourceFailure:',result.stderr);self.assertNotIn('DO_NOT_EXPORT_THIS_ERROR',result.stderr)

    def test_cleanup_all_guards_precede_any_targeted_stop(self):
        source=(ROOT/'scripts/cleanup-smal-rolling-original-loaders.ps1').read_text()
        self.assertLess(len(source.encode()),6000)
        self.assertNotIn('Remove-Item',source);self.assertNotIn('Stop-VM',source)
        pins={8776:('2026-11-10T13:00:42.5791210Z','d3adac3f72b0a183f032ed5c3df8366b797307849d47e62b7035cacfa1d39934'),11816:('2026-11-10T13:00:43.6199680Z','31925c1e029e90125647f72e3155bc122c919c46087874fdf2da736e2462a88f'),4832:('2026-11-10T13:05:42.8873720Z','217ac5afc96706b8262e3e3c4cf043e7fef7d3e84b19525bba96a0a4be86b935'),11044:('2026-11-10T13:05:43.8813780Z','07267ac2f4db983fd58b5ab7e3cd835e156929969222dd3eb6a3304e7a5b6644')}
        rows=[{'ProcessId':pid,'Name':'powershell.exe','CreationDate':stamp,'CommandLine':'fixture-'+str(pid)} for pid,(stamp,h) in pins.items()]
        for case in ('success','root','node','start','hash','expiry','window'):
            fixture=source.replace('[DateTimeOffset]::UtcNow',"[DateTimeOffset]::Parse('2026-11-10T14:00:00Z')")
            fixture=fixture.replace('catch{$result.errorType=', 'catch{$result.fixtureError=$_.ToString();$result.errorType=')
            for pid,(stamp,h) in pins.items():fixture=fixture.replace(h,hashlib.sha256(('fixture-'+str(pid)).encode()).hexdigest())
            if case=='expiry':fixture=fixture.replace("$expiry=[DateTimeOffset]::Parse('2026-11-10T15:20:00+02:00')","$expiry=[DateTimeOffset]::Parse('2026-11-10T17:20:00+02:00')")
            if case=='window':fixture=fixture.replace("$end=[DateTimeOffset]::Parse('2026-11-10T17:00:00+02:00')","$end=[DateTimeOffset]::Parse('2026-11-10T15:59:00+02:00')")
            pre="$env:COMPUTERNAME='LocalBox-Client';$global:Stops=@();$global:Rows=ConvertFrom-Json '"+json.dumps(rows)+"';foreach($p in $global:Rows){$p.CreationDate=[datetime]$p.CreationDate}\n"
            pre+="$global:FixtureRootPresent=$"+str(case=='root').lower()+";$global:FixtureBadNode=$"+str(case=='node').lower()+"\n"
            if case=='start':pre+="$global:Rows[0].CreationDate=$global:Rows[0].CreationDate.AddSeconds(1)\n"
            if case=='hash':pre+="$global:Rows[0].CommandLine='changed'\n"
            pre+="""
function Test-Path {param($LiteralPath) return $global:FixtureRootPresent}
function Join-Path {param($Path,$ChildPath) return ($Path+'\'+$ChildPath)}
function Get-VM {param($Id,$ErrorAction) [pscustomobject]@{Id=[guid]'12a44e0c-cc08-4c4c-a812-fa0b56efdbc3';Name='LB-NODE02';State='Running';ProcessorCount=$(if($global:FixtureBadNode){16}else{8});MemoryStartup=68719476736}}
function Get-CimInstance {param($ClassName,$Filter,$OperationTimeoutSec,$ErrorAction) return $global:Rows}
function Get-Process {param($Id,$ErrorAction) $r=@($global:Rows|Where-Object ProcessId -EQ $Id)[0];$p=[pscustomobject]@{Id=$Id;Handle=1;StartTime=$r.CreationDate;HasExited=$false};$p|Add-Member ScriptMethod WaitForExit {param($n) $true};$p|Add-Member ScriptMethod Dispose {};$p}
function Stop-Process {param($InputObject,[switch]$Force,$ErrorAction) $global:Stops+=$InputObject.Id;$global:Rows=@($global:Rows|Where-Object ProcessId -NE $InputObject.Id)}
"""
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)/'cleanup-fixture.ps1';path.write_text(pre+fixture+"\n@{stops=@($global:Stops)}|ConvertTo-Json -Compress\n")
                result=subprocess.run(['pwsh','-NoLogo','-NoProfile','-NonInteractive','-File',str(path)],capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                values=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
                if case=='success':self.assertEqual(set(values[-1]['stops']),set(pins),result.stdout);self.assertEqual(values[0]['status'],'exact-loaders-absent-node-unchanged')
                else:self.assertEqual(values[-1]['stops'],[]);self.assertEqual(values[0]['status'],'refused')


if __name__=='__main__':unittest.main()
