# GET-only reconciliation of the exact original invocation. Receipt age is provenance.
$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -ine 'LocalBox-Client'){throw 'Wrong outer host'}
$stage='moc-add-LB-NODE02';$root='C:\ProgramData\AzureLocalBox\ServiceReturn-20261111-01'
$transport='C:\ProgramData\AzureLocalBox\CommandTransport\node02-moc-restore-20261111-01'
$source=Get-Item -LiteralPath (Join-Path $transport 'command.ps1')
$sourceSha=(Get-FileHash -LiteralPath $source.FullName).Hash.ToLowerInvariant()
if($sourceSha -cne '43f3aec0480b68048f9fa4a2daa6b1d523a72e7eb9c0c6ad676a222a8b49bb9d'){throw 'Exact original executed source differs'}
$started=Get-Content (Join-Path $transport 'execution-started.json') -Raw|ConvertFrom-Json
$p=Get-Process -Id $started.pid -ErrorAction SilentlyContinue
$currentStart=if($p){$p.StartTime.ToUniversalTime()}else{$null}
$originalAbsent=$null -eq $p -or $currentStart -gt [DateTimeOffset]::Parse($started.atUtc).UtcDateTime
$files=@();$op=$null
if(Test-Path -LiteralPath $root){
 foreach($f in @(Get-ChildItem -LiteralPath $root -File)){
  if($f.Length -gt 524288 -or ($f.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Control evidence bound/path differs'}
  $record=if($f.Extension -ieq '.json'){Get-Content -LiteralPath $f.FullName -Raw|ConvertFrom-Json}else{$null}
  $files+=,@{name=$f.Name;sha256=(Get-FileHash -LiteralPath $f.FullName).Hash.ToLowerInvariant();bytes=$f.Length;createdAtUtc=$f.CreationTimeUtc.ToString('o');lastWriteAtUtc=$f.LastWriteTimeUtc.ToString('o');record=$record}
  if($f.Name -ieq 'operation.json'){$op=$record}
 }
}
$stageArtifacts=@($files|Where-Object {$_.name.Contains($stage)})
$sameOperation=$null -ne $op -and $op.operationId -ceq 'smal-node02-service-return-20261111-01' -and $op.planSha256 -ceq '5af72b1a487ba8f0f4d01fe58cff44f4670d3a6ffb7eae8b0b970b254c90faa1'
$noRpc=$originalAbsent -and $stageArtifacts.Count -eq 0 -and ($files.Count -eq 0 -or ($files.Count -eq 1 -and $sameOperation))
$apiObserved=[DateTimeOffset]::Parse('2026-11-11T09:59:52.054866+02:00')
$invocationAt=[DateTimeOffset]::Parse($started.atUtc)
@{status='exact-original-attempt-control-GET';mutationPerformed=$false;originalExecutedSourceSha256=$sourceSha;originalInvocation=@{pid=$started.pid;executionStartedAtUtc=$started.atUtc;currentPidStartUtc=$(if($currentStart){$currentStart.ToString('o')}else{$null});originalIdentityAbsent=$originalAbsent};rootPresent=(Test-Path -LiteralPath $root);files=$files;stageArtifactCount=$stageArtifacts.Count;sourceOrderNoRpcProved=$noRpc;originalApiEvidenceAgeAtInvocationSeconds=($invocationAt-$apiObserved).TotalSeconds;originalCompiledFiveMinuteGuardAlreadyExpired=($invocationAt-$apiObserved).TotalSeconds -gt 300;proofBasis='Exact original synchronous source writes create-only request and rpc-pending state/event BEFORE its only mutation. Original process absent plus no stage artefact proves no RPC. Otherwise the outcome remains unknown.';originalSourceOrRecordsChanged=$false;actualMocMembershipClaimed=$false;atUtc=[datetime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 20 -Compress
