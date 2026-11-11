"""One dated read-only MOC-return baseline, using reviewed implementations. No native calls."""
import hashlib,importlib.util,json
from pathlib import Path
R=Path(__file__).resolve().parent
OLD=Path('/tmp/opencode/smal-service-return-20261110-04/phase04.py')
assert hashlib.sha256(OLD.read_bytes()).hexdigest()=='e74219a77cd05825ad2f3df9ddd66afd010d28785216b6abe70f22f0e570f469'
spec=importlib.util.spec_from_file_location('_reference04',OLD);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
sha=lambda b:hashlib.sha256(b).hexdigest()
def build():
 text=old.read_source()
 text=text.replace('2026-11-10T23:40:00+02:00','2026-11-11T15:20:00+02:00').replace('smal-node02-service-return-20261110-04','smal-node02-service-return-20261111-01')
 # Current protection is observed, not preaccepted from the expired760c policy.
 text=text.replace(" Assert-Compute ($actualSnapshotFingerprint -ceq $AcceptedProtectorFingerprint) 'PROTECTION: actual new fingerprint differs from explicit acceptance'",' # Current opaque fingerprint reported for NEW dated coordinator acceptance; no baseline rewrite.')
 old_call=' Assert-ProtectionProfiles $snapshot $row.beforeProfiles $row.beforeStates'
 assert text.count(old_call)==1
 text=text.replace(old_call,' Assert-MorningReadProfiles $snapshot $row.beforeProfiles $row.beforeStates')
 marker='@{ id = $_.UniqueId; owner = $ownerMap[$_.UniqueId]; health ='
 assert text.count(marker)==1
 text=text.replace(marker,"@{ id = $_.UniqueId; objectId = $_.ObjectId; uniqueIdFormat = [string]$_.UniqueIdFormat; serialNumber = $_.SerialNumber; physicalLocation = $_.PhysicalLocation; size = $_.Size; owner = $ownerMap[$_.UniqueId]; health =")
 helper=r"""
function Assert-MorningReadProfiles($snapshot,$profiles,$states){
 Assert-ComputeEqual $snapshot.hostStatic $reference03.baseline.hostStatic 'Morning read: host static drift'
 Assert-ComputeEqual $snapshot.volumesStatic $reference03.baseline.volumesStatic 'Morning read: volume static drift'
 Assert-Compute ($snapshot.guestsStatic.Count -eq 4) 'Morning read: exact four VMs required'
 foreach($g in $snapshot.guestsStatic){
  $p=$profiles.PSObject.Properties[$g.name].Value
  Assert-Compute ($g.cpu -eq $p.cpu -and $g.memory -eq $p.memory -and $snapshot.states[$g.name] -ceq $states.PSObject.Properties[$g.name].Value) 'Morning read: current partial profile/state differs'
  $b=@($reference03.baseline.guestsStatic|Where-Object name -CEQ $g.name)
  Assert-Compute ($b.Count -eq 1) 'Morning read: original VM identity absent'
  $expected=@{};foreach($p in $b[0].PSObject.Properties){if($p.Name -cnotin @('cpu','memory','protectorHash')){$expected[$p.Name]=$p.Value}}
  $actual=@{};foreach($k in $g.Keys){if($k -cnotin @('cpu','memory','protectorHash')){$actual[$k]=$g[$k]}}
  Assert-ComputeEqual $actual $expected 'Morning read: non-protector VM/VHD/NIC/security static drift'
 }
}
"""
 text+=helper+r"""
$o=Read-ServiceReturn04
Assert-MocOnlyOriginal03 $o
$fingerprints=@($o.hostSnapshot.guestsStatic|ForEach-Object {$g=$_;@{name=$g.name;vmId=$g.id;actualProtectorHash=$g.protectorHash;originalSealedProtectorHash=(@($reference03.baseline.guestsStatic|Where-Object name -CEQ $g.name)[0]).protectorHash}})
@{status='complete-new-day-service-return-read-not-go';operationId='smal-node02-service-return-20261111-01';hardStopSast='2026-11-11T15:20:00+02:00';old03DeadlineUnchanged='2026-11-10T23:30:00+02:00';referenceJobPolicy34342aIsConfigurationNotCurrentAuthority=$true;currentFingerprintsRequireNewCoordinatorAcceptance=$true;currentProtectionAcceptedForEffect=$false;evidence=$o;currentVmProtectorFingerprints=$fingerprints;newNativeGoIssued=$false;rawObservationRewritten=$false;atUtc=[datetime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 60 -Compress
"""
 return text
if __name__=='__main__':
 s=build();p=R/'read-smal-node02-service-return-baseline-20261111-01.ps1'
 if p.exists():assert p.read_bytes()==s.encode()
 else:p.write_text(s)
 print(json.dumps({'source':str(p),'sha256':sha(s.encode()),'nativeExecuted':False},indent=2))
