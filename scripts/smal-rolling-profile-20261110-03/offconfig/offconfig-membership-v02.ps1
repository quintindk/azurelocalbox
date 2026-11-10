# Accepted qv02 native-string membership algorithm, scoped only to Off NODE02's peer.
function Assert-OffconfigMocMembershipV02($read){
 Assert-Compute ($read.qualified -eq $true -and $read.membershipObserved -eq $true -and $read.observerNode -ceq 'LB-NODE01') 'OFFCONFIG: actual MOC observer unqualified or wrong peer'
 $binding=Get-ComputeField (Get-ComputeField $plan.mocContract 'nodes') $read.observerNode
 Assert-Compute ($null -ne $binding) 'OFFCONFIG: pinned installed MOC peer binding missing'
 Assert-ComputeEqual $read.commands (Get-ComputeField $binding 'commands') 'Installed MOC module/signature/required-parameter contract differs'
 $names=[Collections.Generic.List[string]]::new()
 $unique=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
 foreach($member in @($read.members)){
  $scalar=$member
  if($scalar -is [Management.Automation.PSObject]){$scalar=$scalar.PSObject.BaseObject}
  Assert-Compute ($scalar -is [string]) 'OFFCONFIG: MOC member is not a native string scalar'
  Assert-Compute ($scalar -cin @('LB-NODE01','LB-NODE03')) 'OFFCONFIG: unknown/noncanonical MOC member'
  Assert-Compute ($unique.Add([string]$scalar)) 'OFFCONFIG: duplicate native MOC member'
  $names.Add([string]$scalar)
 }
 Assert-Compute ($names.Count -eq 2) 'OFFCONFIG: exact excluded-NODE02 MOC membership required'
 $sorted=$names.ToArray();[Array]::Sort($sorted,[StringComparer]::Ordinal)
 $expected=@('LB-NODE01','LB-NODE03')
 for($i=0;$i -lt 2;$i++){Assert-Compute ([string]::Equals([string]$sorted[$i],[string]$expected[$i],[StringComparison]::Ordinal)) 'OFFCONFIG: exact canonical MOC membership differs'}
}
