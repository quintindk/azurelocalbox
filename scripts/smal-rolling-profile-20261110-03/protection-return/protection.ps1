# Two compensating keys only. Actual observations and the sealed plan are never rewritten.
$ProtectionDecisionSha256='760c52bc70211d0819671bd5c8ed05a1e20fc1119652a45ec204294c444573f5'
$AcceptedProtectorFingerprint='F99FFFC3698A0D11DA8BD060F89228314CCEB4B67B58A218D97835F87FB1D315'
function Read-ProtectionCurrent([string]$actualSnapshotFingerprint){
 $vm=Get-VM -Id '12a44e0c-cc08-4c4c-a812-fa0b56efdbc3' -ErrorAction Stop
 Assert-Compute ($vm.Name -ceq 'LB-NODE02' -and $vm.State.ToString() -ceq 'Running' -and $vm.ProcessorCount -eq 20 -and $vm.MemoryStartup -eq 96GB -and $vm.MemoryAssigned -eq 96GB) 'PROTECTION: exact Running20/96/assigned96 VM required'
 Assert-Compute ($actualSnapshotFingerprint -ceq $AcceptedProtectorFingerprint) 'PROTECTION: actual new fingerprint differs from explicit acceptance'
 $s=Get-VMSecurity -VM $vm -ErrorAction Stop;$f=Get-VMFirmware -VM $vm -ErrorAction Stop
 Assert-Compute ($s.TpmEnabled -eq $true -and $s.Shielded -eq $false -and $s.EncryptStateAndVmMigrationTraffic -eq $false -and $s.BindToHostTpm -eq $false -and $s.VirtualizationBasedSecurityOptOut -eq $false) 'PROTECTION: current typed security flags differ'
 Assert-Compute ($f.SecureBoot.ToString() -ceq 'On' -and $f.SecureBootTemplate -ceq 'MicrosoftWindows' -and $f.SecureBootTemplateId.ToString() -ieq '1734c6e8-3154-4dda-ba5f-a874cc483422') 'PROTECTION: current SecureBoot/template differs'
 $cmd=@(Get-Command -Name Get-HgsGuardian -All -ErrorAction Stop)
 Assert-Compute ($cmd.Count -eq 1 -and $cmd[0].ModuleName -ceq 'HgsClient' -and $cmd[0].Module.Version.ToString() -ceq '1.0.0.0' -and $cmd[0].Parameters.ContainsKey('Name') -and (Get-FileHash -LiteralPath $cmd[0].Module.Path).Hash.ToLowerInvariant() -ceq '5fa7d08fef65bef57ac9eda552aadc18712d6fdc7b83c946165cbaa52f202ce4') 'PROTECTION: qualified current HGS GET binding differs'
 $g=@(& $cmd[0] -Name 'LB-LocalGuardian' -ErrorAction Stop)
 Assert-Compute ($g.Count -eq 1 -and $g[0].Name -ceq 'LB-LocalGuardian') 'PROTECTION: current named guardian differs'
 $certs=@();$expected=@{SigningCertificate='D8E5AE04977608B123BAE84E6FA825C8B7477B4B';EncryptionCertificate='621A57E97AD851C25A66FCD8DF4A0200A0F17CE9'}
 foreach($name in @('SigningCertificate','EncryptionCertificate')){
  $c=$g[0].PSObject.Properties[$name].Value
  Assert-Compute ($c -is [Security.Cryptography.X509Certificates.X509Certificate2] -and $c.Thumbprint -ceq $expected[$name] -and $c.NotBefore.ToUniversalTime() -le [datetime]::UtcNow -and [datetime]::UtcNow -le $c.NotAfter.ToUniversalTime()) 'PROTECTION: current public certificate/thumbprint/validity differs'
  $certs+=@{property=$name;thumbprint=$c.Thumbprint;notBeforeUtc=$c.NotBefore.ToUniversalTime().ToString('o');notAfterUtc=$c.NotAfter.ToUniversalTime().ToString('o');currentlyWithinValidity=$true;privateKeyAccessed=$false}
 }
 @{vmId=$vm.Id.ToString();state='Running';cpu=$vm.ProcessorCount;startupMemoryBytes=$vm.MemoryStartup;assignedMemoryBytes=$vm.MemoryAssigned;protectorFingerprint=$actualSnapshotFingerprint;tpmEnabled=$s.TpmEnabled;secureBoot=$f.SecureBoot.ToString();secureBootTemplate=$f.SecureBootTemplate;secureBootTemplateId=$f.SecureBootTemplateId.ToString();guardianName=$g[0].Name;publicCertificates=$certs;causeEstablished=$false;semanticRekeyInferred=$false;ownerRelationshipDecoded=$false;chainTrustVerified=$false;atUtc=[datetime]::UtcNow.ToString('o')}
}
function Assert-ProtectionProfiles($snapshot,$profiles,$states){
 Assert-Compute ($stage -cin @('resume-LB-NODE02','moc-add-LB-NODE02')) 'PROTECTION: outside the two compensating keys'
 Assert-ComputeEqual $snapshot.hostStatic $plan.baseline.hostStatic 'PROTECTION: original outer host drift'
 Assert-ComputeEqual $snapshot.volumesStatic $plan.baseline.volumesStatic 'PROTECTION: original volume identity drift'
 Assert-Compute ($snapshot.guestsStatic.Count -eq 4) 'PROTECTION: original four VMs required'
 foreach($g in $snapshot.guestsStatic){
  $profile=$profiles.PSObject.Properties[$g.name].Value
  Assert-Compute ($null -ne $profile -and $g.cpu -eq $profile.cpu -and $g.memory -eq $profile.memory -and $snapshot.states[$g.name] -ceq $states.PSObject.Properties[$g.name].Value) 'PROTECTION: exact stage profile/state differs'
  $original=@($plan.baseline.guestsStatic|Where-Object name -CEQ $g.name)
  Assert-Compute ($original.Count -eq 1) 'PROTECTION: original VM identity absent'
  $expected=@{};foreach($p in $original[0].PSObject.Properties){if($p.Name -cnotin @('cpu','memory')){$expected[$p.Name]=$p.Value}}
  if($g.name -ceq 'LB-NODE02'){
   Assert-Compute ($expected.protectorHash -ceq '9ED1D6E402D9DA2B283F03D3986E6E69A8E79658801BFFC70A7D1CC7E4EA7FC5') 'PROTECTION: immutable old baseline fingerprint changed'
   $expected.protectorHash=$AcceptedProtectorFingerprint
  }
  $actual=@{};foreach($key in $g.Keys){if($key -cnotin @('cpu','memory')){$actual[$key]=$g[$key]}}
  # This is an EXPECTED projection, not a modified raw snapshot or sealed baseline.
  Assert-ComputeEqual $actual $expected 'PROTECTION: current nonprofile static differs from explicit expected projection'
 }
}
function Assert-ProtectionMoc($read,[string[]]$expected,$contract){
 Assert-Compute ($read.qualified -eq $true -and $read.membershipObserved -eq $true -and $read.observerNode -ceq 'LB-NODE01') 'PROTECTION: qualified exact peer required'
 Assert-ComputeEqual $read.commands $contract.nodes.'LB-NODE01'.commands 'PROTECTION: installed MOC bindings differ'
 $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal);$names=[Collections.Generic.List[string]]::new()
 foreach($member in @($read.members)){$n=$member;if($n -is [Management.Automation.PSObject]){$n=$n.PSObject.BaseObject};Assert-Compute ($n -is [string] -and $n -cin @('LB-NODE01','LB-NODE02','LB-NODE03')) 'PROTECTION: noncanonical MOC member';Assert-Compute ($seen.Add([string]$n)) 'PROTECTION: duplicate MOC member';$names.Add([string]$n)}
 Assert-Compute ($names.Count -eq $expected.Count) 'PROTECTION: exact membership count differs'
 $actual=$names.ToArray();[Array]::Sort($actual,[StringComparer]::Ordinal);[Array]::Sort($expected,[StringComparer]::Ordinal)
 for($i=0;$i -lt $expected.Count;$i++){Assert-Compute ([string]::Equals($actual[$i],$expected[$i],[StringComparison]::Ordinal)) 'PROTECTION: actual membership differs'}
}
function Assert-ProtectionAuthority {
 Assert-Compute ($stage -cin @('resume-LB-NODE02','moc-add-LB-NODE02') -and $ProtectionProof.protectionDecisionSha256 -ceq $ProtectionDecisionSha256 -and $ProtectionProof.reviewedOverlaySha256 -ceq $ProtectionOverlaySha256) 'PROTECTION: exact limited decision/source QA required'
 $now=[DateTimeOffset]::UtcNow
 foreach($at in @($ProtectionProof.observedAt,$ProtectionProof.entitlementObservedAtUtc)){$age=($now-[DateTimeOffset]::Parse($at)).TotalSeconds;Assert-Compute ($age -ge 0 -and $age -le 300) 'PROTECTION: stale/future native or API observation'}
 Assert-Compute ($ProtectionProof.entitlementReceiptSha256 -ceq $plan.entitlement.receiptSha256 -and $ProtectionProof.freshEntitlementReceiptSha256 -cne $plan.entitlement.receiptSha256 -and [DateTimeOffset]::Parse($ProtectionProof.entitlementObservationProvenance.earliestOwnerExpiryUtc) -ge [DateTimeOffset]::Parse($plan.executionApproval.expiresAt) -and $now -lt [DateTimeOffset]::Parse($plan.executionApproval.expiresAt)) 'PROTECTION: current authority/original bound insufficient'
}
