$ErrorActionPreference='Stop'
$ComputeCapacityLibraryOnly=$true
$entry=$null
if($env:COMPUTERNAME -cne 'LocalBox-Client'){throw 'Wrong outer host'}
$deadline=[DateTimeOffset]::Parse('2026-11-10T15:00:00+02:00')
if([DateTimeOffset]::UtcNow -ge $deadline){throw 'Fixed MOC qualifier window closed'}
$plan=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('eyJndWVzdElkcyI6eyJMQi1EQzAxIjoiZjk0YzcxZjEtNjg1NC00OGI5LWE5ZjEtODIzOGM5OTM2NmQwIiwiTEItTk9ERTAxIjoiM2FkZmY2MjktMmY2Ny00NDliLWFiMzItOGE4NzQ4YzQ2ZjM0IiwiTEItTk9ERTAyIjoiMTJhNDRlMGMtY2MwOC00YzRjLWE4MTItZmEwYjU2ZWZkYmMzIiwiTEItTk9ERTAzIjoiNWI2ZWJhMTUtZmE4Mi00ZTEyLTllNDUtNWZmYmNkNDhjOGE5In0sInRyYW5zaXRpb25Db250cmFjdCI6eyJkZXZpY2VPd25lcnMiOnt9fX0='))|ConvertFrom-Json)
function Assert-Compute([bool]$condition, [string]$message) {
    if (-not $condition) { throw $message }
}
function New-ComputeSession([string]$name) {
    $id = $plan.guestIds.PSObject.Properties[$name].Value
    $vm = Get-VM -Id $id
    Assert-Compute ($vm.Name -ceq $name -and $vm.State.ToString() -ceq 'Running') 'Exact Running node required'
    $boot = 'C:\ProgramData\AzureLocalBox\Bootstrap\guest-bootstrap-20261028-01'
    $bundle = Get-Content (Join-Path $boot 'bundle.json') -Raw | ConvertFrom-Json
    $entry = @($bundle.files | Where-Object name -CEQ 'smal-guest-secret-functions.ps1')
    $helper = Join-Path $boot 'smal-guest-secret-functions.ps1'
    Assert-Compute ($entry.Count -eq 1 -and (Get-FileHash $helper).Hash -ceq $entry[0].sha256) 'Existing secret helper differs'
    . $helper
    $store = 'C:\ProgramData\AzureLocalBox\Bootstrap\cluster-prereqs-20261028-01\secrets'
    $bindings = Get-Content 'C:\ProgramData\AzureLocalBox\Bootstrap\cluster-prereqs-20261028-01\credential-bindings.json' -Raw | ConvertFrom-Json
    $binding = $bindings.nodes.PSObject.Properties[$name].Value
    Assert-Compute ($binding.vmId -ieq $id -and $binding.role -ceq 'cluster-node-admin' -and $binding.secretDirectory -ceq $store -and $binding.loginVerified -eq $true) 'Existing credential binding differs'
    $secure = Read-LabGuestSecureSecret -SecretDirectory $store -Role 'cluster-node-admin'
    try {
        # Exactly one authentication attempt. No old account-name fallback.
        return New-PSSession -VMId $vm.Id -Credential ([pscredential]::new(($name + '\ASBuiltInAdmin'), $secure)) -ErrorAction Stop
    } finally { $secure.Dispose() }
}

# Exact GET-only installed-command/membership qualification. No command bodies exported.
$ProfileMocRead = {
    param([string]$expectedNode, [bool]$metadataOnly = $false)
    $ErrorActionPreference = 'Stop'
    if ($expectedNode -cnotin @('LB-NODE01','LB-NODE02','LB-NODE03') -or $env:COMPUTERNAME -cne $expectedNode) { throw 'Exact MOC observer node differs' }
    $admin = Get-LocalUser -Name ASBuiltInAdmin
    if (-not $admin.Enabled -or -not $admin.SID.Value.EndsWith('-500') -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne $admin.SID.Value) { throw 'MOC observer RID 500 differs' }
    function Hash-ProfileMoc([string]$text) {
        $hash = [Security.Cryptography.SHA256]::Create()
        try { return [BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($text))).Replace('-', '').ToLowerInvariant() } finally { $hash.Dispose() }
    }
    $commands = [ordered]@{}
    $issues = @()
    foreach ($name in @('Get-MocPhysicalNode','Remove-MocPhysicalNode','New-MocPhysicalNode')) {
        $found = @(Get-Command -Name $name -All -ErrorAction SilentlyContinue)
        if ($found.Count -ne 1) {
            if (-not $metadataOnly) { throw 'Unique installed module-backed MOC command required' }
            $issues += ($name + ': unique installed command missing')
            $commands[$name] = @{ name = $name; matches = @($found | ForEach-Object { @{ name = $_.Name; commandType = $_.CommandType.ToString(); moduleName = $_.ModuleName } }) }
            continue
        }
        $command = $found[0]
        if ($command.Name -cne $name -or $command.CommandType.ToString() -cnotin @('Function','Cmdlet') -or -not $command.ModuleName -or -not $command.Module.Path) { $issues += ($name + ': module-backed function/cmdlet required') }
        $sets = @($command.ParameterSets | Sort-Object Name | ForEach-Object {
            [ordered]@{ name = $_.Name; isDefault = $_.IsDefault; parameters = @($_.Parameters | Sort-Object Name | ForEach-Object { [ordered]@{ name = $_.Name; type = $_.ParameterType.FullName; mandatory = $_.IsMandatory } }) }
        })
        $valid = @($sets | Where-Object {
            if ($name -ceq 'Get-MocPhysicalNode') { @($_.parameters | Where-Object mandatory -EQ $true).Count -eq 0 }
            else { @($_.parameters | Where-Object { $_.name -ceq 'NodeName' -and $_.type -cin @('System.String','System.String[]') }).Count -eq 1 -and @($_.parameters | Where-Object { $_.mandatory -and $_.name -cne 'NodeName' }).Count -eq 0 }
        })
        if ($valid.Count -eq 0 -or ($valid.Count -gt 1 -and @($valid | Where-Object isDefault -EQ $true).Count -ne 1)) { $issues += ($name + ': official no-extra-argument/NodeName-only binding unsupported or ambiguous') }
        $descriptor = [ordered]@{ name = $name; commandType = $command.CommandType.ToString(); moduleName = $command.ModuleName; moduleVersion = $(if ($command.Module) { $command.Module.Version.ToString() } else { $null }); moduleGuid = $(if ($command.Module) { $command.Module.Guid.ToString() } else { $null }); modulePath = $command.Module.Path; moduleSha256 = $(if ($command.Module.Path) { (Get-FileHash -LiteralPath $command.Module.Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant() } else { $null }); definitionSha256 = Hash-ProfileMoc $command.Definition; parameterSets = $sets }
        $descriptor.contractSha256 = Hash-ProfileMoc ($descriptor | ConvertTo-Json -Depth 20 -Compress)
        $commands[$name] = $descriptor
    }
    if ($issues.Count -gt 0) {
        if (-not $metadataOnly) { throw 'Installed MOC module/signature/required-parameter qualification failed' }
        return [ordered]@{ qualified = $false; observerNode = $expectedNode; commands = $commands; qualificationIssues = @($issues); members = $null; membershipObserved = $false; atUtc = [datetime]::UtcNow.ToString('o') }
    }
    $getter = @(Get-Command -Name Get-MocPhysicalNode -All -ErrorAction Stop)
    if ($getter.Count -ne 1) { throw 'MOC getter changed during qualification' }
    $rows = @(& $getter[0])
    $members = @($rows | ForEach-Object {
        if ($null -eq $_.PSObject.Properties['NodeName'] -or $_.NodeName -cnotin @('LB-NODE01','LB-NODE02','LB-NODE03')) { throw 'Unknown actual MOC NodeName; no identity inference permitted' }
        [string]$_.NodeName
    } | Sort-Object)
    if (@($members | Select-Object -Unique).Count -ne $members.Count) { throw 'Duplicate actual MOC membership' }
    [ordered]@{ qualified = $true; observerNode = $expectedNode; commands = $commands; members = @($members); membershipObserved = $true; atUtc = [datetime]::UtcNow.ToString('o') }
}
function Read-ProfileMoc([string]$node, [bool]$metadataOnly = $false) {
    $mocSession = New-ComputeSession $node
    try { return Invoke-Command -Session $mocSession -ArgumentList $node, $metadataOnly -ScriptBlock $ProfileMocRead -ErrorAction Stop } finally { Remove-PSSession $mocSession }
}
function Assert-ProfileMocMembership($read, [string[]]$expected, $contract) {
    Assert-Compute ($read.qualified -eq $true -and $read.observerNode -cin @('LB-NODE01','LB-NODE02','LB-NODE03')) 'Qualified exact MOC observer required'
    $binding = Get-ComputeField (Get-ComputeField $contract 'nodes') $read.observerNode
    Assert-Compute ($null -ne $binding) 'Pinned installed MOC observer contract missing'
    Assert-ComputeEqual $read.commands (Get-ComputeField $binding 'commands') 'Installed MOC module/signature/required-parameter contract differs'
    Assert-ComputeEqual @($read.members | Sort-Object) @($expected | Sort-Object) 'Actual MOC membership differs from exact stage'
}


$nodes=[ordered]@{}
foreach($node in @('LB-NODE02','LB-NODE03','LB-NODE01')) {
    if([DateTimeOffset]::UtcNow -ge $deadline){throw 'Fixed MOC qualifier window closed'}
    $nodes[$node]=Read-ProfileMoc $node $true
}
if([DateTimeOffset]::UtcNow -ge $deadline){throw 'Fixed MOC qualifier window closed after reads'}
@{status='complete';mutationPerformed=$false;atUtc=[datetime]::UtcNow.ToString('o');commonSourceSha256='0e58f64f888c897a48b1d4f28bd6faec22346e9d8f1c36e4c92da29f0a2b6b86';nodes=$nodes}|ConvertTo-Json -Depth 30 -Compress
