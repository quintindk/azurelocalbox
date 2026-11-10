# GET-only exact NODE02 opaque-protector/public-guardian and VMMS window metadata.
# No protector/certificate/key bytes, private keys, credential bindings or event messages exported.
$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -cne 'LocalBox-Client'){throw 'Wrong security reader host'}
$deadline=[DateTimeOffset]::Parse('2026-11-10T23:30:00+02:00')
if([DateTimeOffset]::UtcNow -ge $deadline){throw 'Original03 read bound closed'}
$vmId=[guid]'12a44e0c-cc08-4c4c-a812-fa0b56efdbc3'
$originalHash='9ED1D6E402D9DA2B283F03D3986E6E69A8E79658801BFFC70A7D1CC7E4EA7FC5'
$reportedNewHash='F99FFFC3698A0D11DA8BD060F89228314CCEB4B67B58A218D97835F87FB1D315'
function Safe-ReadError($e){@{status='read-error-not-empty';exceptionType=$e.Exception.GetType().FullName;category=[string]$e.CategoryInfo.Category;line=$e.InvocationInfo.ScriptLineNumber;rawMessageSuppressed=$true}}
function Public-Fields($o,[string[]]$names){
 foreach($name in $names){$p=@($o.PSObject.Properties|Where-Object Name -CEQ $name);if($p.Count -ne 1){@{name=$name;present=$false;value=$null};continue};$v=$p[0].Value
  if($null -eq $v){@{name=$name;present=$true;value=$null};continue}
  if($v -is [string] -or $v -is [ValueType]){@{name=$name;present=$true;clrType=$v.GetType().FullName;value=$(if($v -is [DateTime]){$v.ToUniversalTime().ToString('o')}elseif($v -is [Enum]){$v.ToString()}else{$v})}}
  else{@{name=$name;present=$true;clrType=$v.GetType().FullName;unsupportedNonScalar=$true;value=$null}}
 }
}
function Qualified-Getter([string]$name,[string]$module,[string]$parameter){
 $all=@(Get-Command -Name $name -All -ErrorAction Stop)
 if($all.Count -ne 1 -or $all[0].Name -cne $name -or $all[0].ModuleName -cne $module -or $all[0].CommandType.ToString() -cnotin @('Cmdlet','Function')){throw 'Installed GET binding is not unique/qualified'}
 $cmd=$all[0];$sets=@($cmd.ParameterSets|ForEach-Object {@{name=$_.Name;isDefault=$_.IsDefault;parameters=@($_.Parameters|ForEach-Object {@{name=$_.Name;mandatory=$_.IsMandatory;type=$_.ParameterType.FullName}})}})
 $common=@('Verbose','Debug','ErrorAction','WarningAction','InformationAction','ProgressAction','ErrorVariable','WarningVariable','InformationVariable','OutVariable','OutBuffer','PipelineVariable')
 $valid=@($sets|Where-Object {@($_.parameters|Where-Object name -CEQ $parameter).Count -eq 1 -and @($_.parameters|Where-Object {$_.mandatory -and $_.name -cnotin $common -and $_.name -cne $parameter}).Count -eq 0})
 if(-not $valid.Count){throw 'Installed GET parameter set not qualified'}
 @{command=$cmd;descriptor=@{name=$cmd.Name;commandType=$cmd.CommandType.ToString();moduleName=$cmd.ModuleName;moduleVersion=$cmd.Module.Version.ToString();modulePath=$cmd.Module.Path;moduleSha256=$(if($cmd.Module.Path){(Get-FileHash -LiteralPath $cmd.Module.Path -ErrorAction Stop).Hash.ToLowerInvariant()}else{$null});parameterSets=$sets}}
}
$vm=Get-VM -Id $vmId -ErrorAction Stop
if($vm.Name -cne 'LB-NODE02' -or $vm.Id -ne $vmId){throw 'Exact NODE02 VM identity differs'}
$security=Get-VMSecurity -VM $vm -ErrorAction Stop;$firmware=Get-VMFirmware -VM $vm -ErrorAction Stop
$kp=[byte[]](Get-VMKeyProtector -VM $vm -ErrorAction Stop)
if($kp.Length -lt 1 -or $kp.Length -gt 262144){throw 'Opaque protector byte bound differs'}
$hash=[Security.Cryptography.SHA256]::Create()
try{$currentHash=[BitConverter]::ToString($hash.ComputeHash($kp)).Replace('-','')}finally{$hash.Dispose();[Array]::Clear($kp,0,$kp.Length);$kp=$null}
$securityAt=[datetime]::UtcNow.ToString('o')
$guardian=@{status='not-read';expectedNameFromProvisioning='LB-LocalGuardian';expectedPriorPublicId=$null;priorPublicIdentityBaselineAvailable=$false;priorIdNotInvented=$true;getter=$null;objects=$null;error=$null}
try{
 $binding=Qualified-Getter 'Get-HgsGuardian' 'HgsClient' 'Name';$guardian.getter=$binding.descriptor
 $objects=@(& $binding.command -Name 'LB-LocalGuardian' -ErrorAction Stop)
 if($objects.Count -gt 4){throw 'Named guardian result bound exceeded'}
 $guardian.objects=@($objects|ForEach-Object {
  $g=$_;$certificates=@()
  foreach($name in @('SigningCertificate','EncryptionCertificate')){
   $p=@($g.PSObject.Properties|Where-Object Name -CEQ $name)
   if($p.Count -ne 1 -or $null -eq $p[0].Value){$certificates+=@{property=$name;present=($p.Count -eq 1);publicMetadata=$null;status='unavailable-not-assumed'};continue}
   $cert=$p[0].Value
   if($cert -isnot [Security.Cryptography.X509Certificates.X509Certificate2]){$certificates+=@{property=$name;present=$true;clrType=$cert.GetType().FullName;publicMetadata=$null;status='unqualified-certificate-shape'};continue}
   $now=[datetime]::UtcNow
   $certificates+=@{property=$name;present=$true;clrType=$cert.GetType().FullName;status='public-metadata-read';publicMetadata=@{thumbprint=$cert.Thumbprint;subject=$cert.Subject;issuer=$cert.Issuer;serialNumber=$cert.SerialNumber;notBeforeUtc=$cert.NotBefore.ToUniversalTime().ToString('o');notAfterUtc=$cert.NotAfter.ToUniversalTime().ToString('o');currentlyWithinValidity=($cert.NotBefore.ToUniversalTime() -le $now -and $now -le $cert.NotAfter.ToUniversalTime());hasPrivateKey=$cert.HasPrivateKey;certificateBytesExported=$false;privateKeyAccessed=$false;chainTrustVerified=$false}}
  }
  @{clrType=$g.GetType().FullName;publicIdentity=@(Public-Fields $g @('Name','Id','InstanceId','GuardianId'));availablePropertyNames=@($g.PSObject.Properties.Name|Select-Object -First 64);certificates=$certificates}
 });$guardian.status='read';$guardian.atUtc=[datetime]::UtcNow.ToString('o')
}catch{$guardian.status='failed-not-empty';$guardian.error=Safe-ReadError $_}

# Discover installed VMMS logs. No guessed event IDs, messages or bulk event payloads.
$events=@{windowStartSast='2026-11-10T22:40:00+02:00';windowEndSast='2026-11-10T22:42:00+02:00';status='not-read';getter=$null;logs=$null;error=$null}
try{
 $binding=Qualified-Getter 'Get-WinEvent' 'Microsoft.PowerShell.Diagnostics' 'ListLog';$events.getter=$binding.descriptor
 $eventCmd=$binding.command
 if(-not $eventCmd.Parameters.ContainsKey('FilterHashtable') -or -not $eventCmd.Parameters.ContainsKey('MaxEvents')){throw 'Installed bounded event GET signature unavailable'}
 $logs=@(& $eventCmd -ListLog '*Hyper-V-VMMS*' -ErrorAction Stop)
 if($logs.Count -gt 8){throw 'VMMS log discovery bound exceeded'}
 $events.logs=@();$start=[DateTimeOffset]::Parse($events.windowStartSast).UtcDateTime;$finish=[DateTimeOffset]::Parse($events.windowEndSast).UtcDateTime
 foreach($log in $logs){
  if($log.LogName -notlike '*Hyper-V-VMMS*'){throw 'Discovered log outside exact VMMS provider scope'}
  $out=@{logName=$log.LogName;enabled=$log.IsEnabled;logType=[string]$log.LogType;status='not-queried';scannedCount=$null;truncated=$false;matchingVmEvents=$null;error=$null};$events.logs+=,$out
  if(-not $log.IsEnabled -or [string]$log.LogType -cnotin @('Administrative','Operational')){continue}
  try{
   $records=@(& $eventCmd -FilterHashtable @{LogName=$log.LogName;StartTime=$start;EndTime=$finish} -MaxEvents 129 -ErrorAction Stop)
   $out.scannedCount=$records.Count;$out.truncated=$records.Count -gt 128;$out.matchingVmEvents=@()
   foreach($event in @($records|Select-Object -First 128)){
    $xml=[xml]$event.ToXml();$leaves=@($xml.SelectNodes('//*[not(*)]'))
    if($leaves.Count -gt 128){throw 'Single event metadata bound exceeded'}
    $matches=@();$names=@()
    foreach($leaf in $leaves){
     $name=if($leaf.LocalName -ceq 'Data'){$leaf.GetAttribute('Name')}else{$leaf.LocalName}
     if($name -cmatch '^[A-Za-z_][A-Za-z0-9_.-]{0,79}$'){$names+=,$name}
     $parsed=[guid]::Empty
     if([guid]::TryParse([string]$leaf.InnerText,[ref]$parsed) -and $parsed -eq $vmId){$matches+=,$name}
     elseif($name -cin @('VmName','VMName','VirtualMachineName') -and [string]::Equals([string]$leaf.InnerText,'LB-NODE02',[StringComparison]::Ordinal)){$matches+=,$name}
    }
    if(-not $matches.Count){continue}
    if($out.matchingVmEvents.Count -ge 32){$out.truncated=$true;break}
    $protectorMention=$false
    try{$protectorMention=[string]$event.Message -match '(?i)(key.?protector|guardian|\bTPM\b|shield)'}catch{}
    $out.matchingVmEvents+=@{id=$event.Id;recordId=$event.RecordId;providerName=$event.ProviderName;logName=$event.LogName;timeCreatedUtc=$event.TimeCreated.ToUniversalTime().ToString('o');level=$event.Level;task=$event.Task;opcode=$event.Opcode;activityId=[string]$xml.Event.System.Correlation.ActivityID;relatedActivityId=[string]$xml.Event.System.Correlation.RelatedActivityID;exactVmIdentityMatchedFields=$matches;dataFieldNames=@($names|Select-Object -Unique -First 64);protectorTermsMentionedInRenderedMessage=$protectorMention;renderedMessageExported=$false;eventDataValuesExported=$false;causalityEstablished=$false}
   }
   $out.status='metadata-read'
  }catch{if($_.FullyQualifiedErrorId.StartsWith('NoMatchingEventsFound',[StringComparison]::Ordinal)){$out.status='no-events-in-exact-window';$out.scannedCount=0;$out.matchingVmEvents=@()}else{$out.status='failed-not-empty';$out.error=Safe-ReadError $_}}
 }
 $events.status='bounded-metadata-read'
}catch{$events.status='failed-not-empty';$events.error=Safe-ReadError $_}
if([DateTimeOffset]::UtcNow -ge $deadline){throw 'Original03 read bound closed after reads'}
@{status='complete-security-metadata-GET-not-compatibility-approval';mutationPerformed=$false;operationId='smal-foundation-profile-20261110-03';planSha256='7ad5e7418dc707dc69d3f48f5330d0aa0ca15125bce7d8fa46a41b99070d338c';vm=@{name=$vm.Name;id=$vm.Id.ToString();state=$vm.State.ToString();generation=$vm.Generation;version=$vm.Version.ToString();cpu=$vm.ProcessorCount;startupMemoryBytes=$vm.MemoryStartup;assignedMemoryBytes=$vm.MemoryAssigned};securityFlags=@(Public-Fields $security @('TpmEnabled','Shielded','EncryptStateAndVmMigrationTraffic','BindToHostTpm','VirtualizationBasedSecurityOptOut'));firmware=@(Public-Fields $firmware @('SecureBoot','SecureBootTemplate','SecureBootTemplateId'));protector=@{algorithm='SHA256';originalSealedFingerprint=$originalHash;reportedNewFingerprint=$reportedNewHash;currentFingerprint=$currentHash;equalsOriginalSealedFingerprint=($currentHash -ceq $originalHash);equalsReportedNewFingerprint=($currentHash -ceq $reportedNewHash);rawBytesExported=$false;observedAtUtc=$securityAt;semanticRekeyInferred=$false;ownerRelationshipDecoded=$false};localGuardian=$guardian;vmmsEvents=$events;provisioningSourceSha256='115ed8b7ef6be7924586d7f0b683b48a1eb4daa05c7ff1384ca3430fb315c8c7';hgsCommandReceiptSha256='7e81734003ee0a6bb107bef0a4b3a16b043137e8abb14dbac0809f81def63abc';knownStart=@{pid=6552;acceptedOriginalObservationSha256='877ebfb8a67709ee2ce0fc410e814f8da5eb1bffc5e75ab4f8ad081eba6f5f98';originalFlagsRewritten=$false};causeEstablished=$false;nativeGoIssued=$false;atUtc=[datetime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 20 -Compress
