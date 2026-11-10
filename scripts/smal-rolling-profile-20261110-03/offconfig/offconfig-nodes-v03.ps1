# Limited off-path only. No deep equality or storage-owner predicate is changed.
function Assert-OffconfigNodeStatesV03($records){
 $script:OffconfigNodeStateFieldTypes=@{containerType=$(if($null -eq $records){'<null>'}else{$records.GetType().FullName});expectedFields=@{name='native string scalar';state='native string scalar'};records=@()}
 $seen=[Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
 $expected=@{'LB-NODE01'='Up';'LB-NODE02'='Down';'LB-NODE03'='Up'}
 foreach($record in @($records)){
  Assert-Compute ($null -ne $record -and $record -isnot [string] -and $record -isnot [ValueType]) 'OFFCONFIG: node-state record is not an object'
  $fields=@(Get-ComputeKeys $record)
  Assert-Compute ($fields.Count -eq 2 -and ($fields-join '|') -ceq 'name|state') 'OFFCONFIG: node-state record requires exact name/state fields'
  $name=Get-ComputeField $record 'name';$state=Get-ComputeField $record 'state'
  $script:OffconfigNodeStateFieldTypes.records+=@{recordType=$record.GetType().FullName;nameType=$(if($null -eq $name){'<null>'}else{$name.GetType().FullName});stateType=$(if($null -eq $state){'<null>'}else{$state.GetType().FullName})}
  if($name -is [Management.Automation.PSObject]){$name=$name.PSObject.BaseObject}
  if($state -is [Management.Automation.PSObject]){$state=$state.PSObject.BaseObject}
  Assert-Compute ($name -is [string] -and $state -is [string]) 'OFFCONFIG: node name/state is not a native string scalar'
  Assert-Compute ($expected.ContainsKey([string]$name)) 'OFFCONFIG: unknown/noncanonical cluster node name'
  Assert-Compute (-not $seen.ContainsKey([string]$name)) 'OFFCONFIG: duplicate canonical cluster node'
  Assert-Compute ([string]::Equals([string]$state,[string]$expected[[string]$name],[StringComparison]::Ordinal)) 'OFFCONFIG: actual canonical node state differs'
  $seen.Add([string]$name,[string]$state)
 }
 Assert-Compute ($seen.Count -eq 3) 'OFFCONFIG: exact three unique canonical node-state records required'
}
