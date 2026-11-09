# Read-only post-deployment inspection. Never resets credentials, storage or services.
$ErrorActionPreference = 'Stop'
$phase = 'host-identity'
try {
if ($env:COMPUTERNAME -cne 'LocalBox-Client') { throw 'Unexpected host' }
$targets = @(@{ name = 'LB-NODE01'; id = '3adff629-2f67-449b-ab32-8a8748c46f34' }, @{ name = 'LB-NODE02'; id = '12a44e0c-cc08-4c4c-a812-fa0b56efdbc3' }, @{ name = 'LB-NODE03'; id = '5b6eba15-fa82-4e12-9e45-5ffbcd48c8a9' })
$boot = 'C:\ProgramData\AzureLocalBox\Bootstrap\guest-bootstrap-20261028-01'
$bundle = Get-Content (Join-Path $boot 'bundle.json') -Raw | ConvertFrom-Json
$entry = @($bundle.files | Where-Object name -CEQ 'smal-guest-secret-functions.ps1'); $helper = Join-Path $boot 'smal-guest-secret-functions.ps1'
if ($entry.Count -ne 1 -or (Get-FileHash $helper).Hash -cne $entry[0].sha256) { throw 'Secret helper differs' }
. $helper
$store = 'C:\ProgramData\AzureLocalBox\Bootstrap\cluster-prereqs-20261028-01\secrets'
$bindings = Get-Content 'C:\ProgramData\AzureLocalBox\Bootstrap\cluster-prereqs-20261028-01\credential-bindings.json' -Raw | ConvertFrom-Json
$nodes = @(foreach ($target in $targets) {
    $vm = Get-VM -Id $target.id; $binding = $bindings.nodes.PSObject.Properties[$target.name].Value
    if ($vm.Name -cne $target.name -or $vm.State.ToString() -ne 'Running' -or $binding.vmId -ine $target.id -or $binding.role -cne 'cluster-node-admin' -or $binding.secretDirectory -cne $store -or $binding.loginVerified -ne $true) { throw 'Exact running guest/credential binding differs' }
    $secure = Read-LabGuestSecureSecret -SecretDirectory $store -Role 'cluster-node-admin'; $session = $null
    try {
        $phase = $target.name + '-credential-session'
        # Documented post-deployment name of RID 500. One attempt, no fallback or reset.
        $session = New-PSSession -VMId $vm.Id -Credential ([pscredential]::new(($vm.Name + '\ASBuiltInAdmin'), $secure)) -ErrorAction Stop
        $phase = $target.name + '-cluster-storage-inspection'
        $guest = Invoke-Command -Session $session -ArgumentList $target.name -ErrorAction Stop -ScriptBlock {
            param($ExpectedName)
            $ErrorActionPreference = 'Stop'
            if ($env:COMPUTERNAME -cne $ExpectedName) { throw 'Guest identity differs' }
            $admin = Get-LocalUser -Name ASBuiltInAdmin
            if (-not $admin.Enabled -or -not $admin.SID.Value.EndsWith('-500') -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne $admin.SID.Value) { throw 'Expected existing RID 500 identity differs' }
            $cluster = Get-Cluster -Name smal-localbox01 -ErrorAction Stop
            $quorum = Get-ClusterQuorum -Cluster $cluster
            $s2d = Get-ClusterStorageSpacesDirect -Node $ExpectedName
            $pools = @(Get-StoragePool | Where-Object IsPrimordial -EQ $false | ForEach-Object {
                $pool = $_
                @{ name = $pool.FriendlyName; uniqueId = $pool.UniqueId; health = $pool.HealthStatus.ToString(); operationalStatus = @($pool.OperationalStatus | ForEach-Object ToString); size = $pool.Size; allocated = $pool.AllocatedSize;
                   members = @($pool | Get-PhysicalDisk | ForEach-Object { @{ uniqueId = $_.UniqueId; size = $_.Size; usage = $_.Usage.ToString(); health = $_.HealthStatus.ToString(); mediaType = $_.MediaType.ToString() } }) }
            })
            @{ name = $env:COMPUTERNAME; observedAdmin = @{ name = $admin.Name; sid = $admin.SID.Value; enabled = $admin.Enabled }; domain = (Get-CimInstance Win32_ComputerSystem).Domain; domainRole = (Get-CimInstance Win32_ComputerSystem).DomainRole;
               clusterName = $cluster.Name; clusterNodes = @(Get-ClusterNode -Cluster $cluster | ForEach-Object { @{ name = $_.Name; state = $_.State.ToString(); nodeWeight = $_.NodeWeight; dynamicWeight = $_.DynamicWeight } });
               quorumType = $quorum.QuorumType.ToString(); quorumResourceName = $(if ($quorum.QuorumResource) { [string]$quorum.QuorumResource.Name } else { $null });
               storageSpacesDirectState = [string]$s2d.State; storagePools = $pools;
               virtualDisks = @(Get-VirtualDisk | ForEach-Object { @{ name = $_.FriendlyName; uniqueId = $_.UniqueId; health = $_.HealthStatus.ToString(); size = $_.Size; footprint = $_.FootprintOnPool; resiliency = $_.ResiliencySettingName; dataCopies = $_.NumberOfDataCopies; provisioning = $_.ProvisioningType.ToString() } });
               csv = @(Get-ClusterSharedVolume -Cluster $cluster | ForEach-Object { @{ name = $_.Name; state = $_.State.ToString(); owner = [string]$_.OwnerNode.Name;
                   volumes = @($_.SharedVolumeInfo | ForEach-Object { @{ path = $_.FriendlyVolumeName; size = $_.Partition.Size; free = $_.Partition.FreeSpace } }) } });
               storageJobs = @(Get-StorageJob | ForEach-Object { @{ name = $_.Name; state = [string]$_.JobState; percentComplete = $_.PercentComplete } });
               localDisks = @(Get-Disk | ForEach-Object { @{ uniqueId = $_.UniqueId; size = $_.Size; isBoot = $_.IsBoot; isSystem = $_.IsSystem } });
               encryption = @(Get-BitLockerVolume | ForEach-Object { @{ mountPoint = $_.MountPoint; volumeType = [string]$_.VolumeType; protectionStatus = [string]$_.ProtectionStatus; encryptionPercentage = $_.EncryptionPercentage; volumeStatus = [string]$_.VolumeStatus } });
               clusterGroups = @(Get-ClusterGroup -Cluster $cluster | ForEach-Object { @{ name = $_.Name; state = $_.State.ToString(); owner = [string]$_.OwnerNode.Name } });
               nestedVms = @(Get-VM | ForEach-Object { @{ name = $_.Name; id = $_.Id.ToString(); state = $_.State.ToString(); memoryBytes = $_.MemoryAssigned } });
               defenderEnabled = (Get-MpComputerStatus).RealTimeProtectionEnabled; firewallEnabled = @(Get-NetFirewallProfile | Where-Object Enabled -NE $true).Count -eq 0;
               services = @(Get-Service -Name himds,GCArcService,ExtensionService,vmms,clussvc -ErrorAction SilentlyContinue | ForEach-Object { @{ name = $_.Name; state = $_.Status.ToString() } }) }
        }
        # Base observation completed above. Optional failures cannot replace it.
        $foundation = $null
        try {
            $foundation = Invoke-Command -Session $session -ArgumentList $target.name -ErrorAction Stop -ScriptBlock {
                param($ExpectedName)
                $ErrorActionPreference = 'Stop'
                # Public metadata only. Definitions are embedded in the reviewed canonical observer.
                # No module import/install, getter invocation, default evaluation or source-body export.
                function ConvertTo-SmalPublicField([string]$Value) {
                    if ([string]::IsNullOrEmpty($Value)) { return @{ status = 'unavailable' } }
                    if ($Value.Length -gt 2048 -or $Value -cmatch '-----BEGIN|\beyJ[A-Za-z0-9_-]{15,}\.|(?i:password|access_token|refresh_token)') {
                        $sha = [Security.Cryptography.SHA256]::Create()
                        try { $digest = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value))).Replace('-', '').ToLowerInvariant() }
                        finally { $sha.Dispose() }
                        return @{ status = 'withheld'; sha256 = $digest }
                    }
                    return @{ status = 'available'; value = $Value }
                }
                function Invoke-SmalOptionalRead([string]$Phase, [scriptblock]$Read) {
                    try { return @{ status = 'complete'; phase = $Phase; value = (& $Read) } }
                    catch { return @{ status = 'failed'; phase = $Phase;
                        errorType = (ConvertTo-SmalPublicField $_.Exception.GetType().FullName);
                        errorCategory = [string]$_.CategoryInfo.Category; sourceLine = [int]$_.InvocationInfo.ScriptLineNumber } }
                }
                function Get-SmalStaticPublicSignatures($Module, [string[]]$Exports) {
                    # Do not resolve types, attributes, defaults, dynamic parameters or nested-module code.
                    $path = [string]$Module.Path
                    if ([IO.Path]::GetExtension($path) -ine '.psm1') {
                        if (-not [string]::IsNullOrEmpty([string]$Module.RootModule)) {
                            $path = [IO.Path]::GetFullPath([IO.Path]::Combine([string]$Module.ModuleBase, [string]$Module.RootModule))
                        }
                    }
                    $base = [IO.Path]::GetFullPath([string]$Module.ModuleBase).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
                    if (-not $path.StartsWith($base, [StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetExtension($path) -ine '.psm1') {
                        return @{ status = 'unavailable-non-script-or-outside-module-root'; complete = $false; signatures = @() }
                    }
                    if (([IO.FileInfo]::new($path)).Length -gt 2097152) {
                        return @{ status = 'unavailable-source-size-bound'; complete = $false; signatures = @() }
                    }
                    $tokens = $null; $parseErrors = $null
                    $ast = [Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$parseErrors)
                    if (@($parseErrors).Count) {
                        return @{ status = 'unavailable-static-parse'; complete = $false; parseIssueCount = @($parseErrors).Count; signatures = @() }
                    }
                    $definitions = @($ast.FindAll({ param($item) $item -is [Management.Automation.Language.FunctionDefinitionAst] -and $item.Name -like 'Get-Moc*' }, $true))
                    $rows = @(foreach ($function in $definitions) {
                        if ($Exports -notcontains $function.Name) { continue }
                        $parameters = @($function.Parameters)
                        if (-not $parameters.Count -and $null -ne $function.Body.ParamBlock) { $parameters = @($function.Body.ParamBlock.Parameters) }
                        @{ name = (ConvertTo-SmalPublicField $function.Name); status = 'declared-static-only';
                           dynamicParameters = $(if ($null -ne $function.Body.DynamicParamBlock) { 'unavailable-not-evaluated' } else { 'not-declared-in-this-function' });
                           parameterSets = 'unavailable-not-resolved';
                           parameters = @(foreach ($parameter in $parameters) {
                               if ($null -eq $parameter) { continue }
                               @{ name = (ConvertTo-SmalPublicField $parameter.Name.VariablePath.UserPath);
                                  declaredTypes = @($parameter.Attributes | Where-Object { $_ -is [Management.Automation.Language.TypeConstraintAst] } | ForEach-Object { ConvertTo-SmalPublicField $_.TypeName.FullName }) }
                           }) }
                    })
                    return @{ status = 'static-metadata-only'; complete = $false; sourcePath = (ConvertTo-SmalPublicField $path);
                        matchedPublicCount = $rows.Count; signatures = $rows }
                }
                function Get-SmalImportedSignature($Command) {
                    $functionAst = $null
                    if ($Command -is [Management.Automation.FunctionInfo]) {
                        $functionAst = $Command.ScriptBlock.Ast
                        if ($functionAst -is [Management.Automation.Language.FunctionDefinitionAst]) { $functionAst = $functionAst.Body }
                    }
                    if (($null -ne $functionAst -and $null -ne $functionAst.DynamicParamBlock) -or
                        ($Command -is [Management.Automation.CmdletInfo] -and @($Command.ImplementingType.GetInterfaces() | Where-Object FullName -EQ 'System.Management.Automation.IDynamicParameters').Count)) {
                        return @{ status = 'unavailable-dynamic-not-evaluated'; complete = $false }
                    }
                    $sets = @($Command.ParameterSets | ForEach-Object {
                            @{ name = (ConvertTo-SmalPublicField $_.Name); parameters = @($_.Parameters | ForEach-Object {
                                @{ name = (ConvertTo-SmalPublicField $_.Name); type = (ConvertTo-SmalPublicField $_.ParameterType.FullName);
                                   mandatory = [bool]$_.IsMandatory }
                            }) }
                        })
                    $unavailable = 0
                    foreach ($set in $sets) {
                        if ($set.name.status -cne 'available') { $unavailable++ }
                        foreach ($parameter in $set.parameters) {
                            if ($parameter.name.status -cne 'available' -or $parameter.type.status -cne 'available') { $unavailable++ }
                        }
                    }
                    return @{ status = 'public-static-metadata'; complete = ($unavailable -eq 0);
                        unavailableFieldCount = $unavailable; parameterSets = $sets }
                }
                function Get-SmalMocPublicMetadata {
                    # Scope-local preference. Never change the existing session/global autoload setting.
                    $PSModuleAutoLoadingPreference = 'None'
                    $WarningPreference = 'SilentlyContinue'; $InformationPreference = 'SilentlyContinue'
                    $VerbosePreference = 'SilentlyContinue'; $DebugPreference = 'SilentlyContinue'; $ProgressPreference = 'SilentlyContinue'
                    $inventoryIssues = @(); $commandIssues = @()
                    $importedModules = @(Get-Module -ErrorAction Stop)
                    $available = @(Get-Module -ListAvailable -ErrorAction SilentlyContinue -ErrorVariable inventoryIssues)
                    $commands = @(Get-Command Get-Moc* -ListImported -CommandType Function,Cmdlet -ErrorAction SilentlyContinue -ErrorVariable commandIssues)
                    $modules = @(foreach ($module in $available) {
                        $exportsProbe = Invoke-SmalOptionalRead 'module-public-export-metadata' { @($module.ExportedCommands.Keys | Where-Object { $_ -like 'Get-Moc*' }) }
                        $exports = @(); if ($exportsProbe.status -eq 'complete') { $exports = @($exportsProbe.value) }
                        if ($module.Name -notlike '*Moc*' -and -not $exports.Count -and $exportsProbe.status -eq 'complete') { continue }
                        $loaded = @($importedModules | Where-Object { $_.Name -ceq $module.Name -and [string]$_.Version -ceq [string]$module.Version -and $_.ModuleBase -ieq $module.ModuleBase }).Count -gt 0
                        @{ name = (ConvertTo-SmalPublicField ([string]$module.Name)); version = (ConvertTo-SmalPublicField ([string]$module.Version));
                           path = (ConvertTo-SmalPublicField ([string]$module.Path)); moduleBase = (ConvertTo-SmalPublicField ([string]$module.ModuleBase));
                           rootModule = (ConvertTo-SmalPublicField ([string]$module.RootModule));
                           importState = $(if ($loaded) { 'imported-exact-name-version-base' } else { 'not-imported' });
                           publicExportsRead = @{ status = [string]$exportsProbe.status; phase = 'module-public-export-metadata';
                               publicGetterCount = $exports.Count; errorCategory = [string]$exportsProbe.errorCategory; sourceLine = [int]$exportsProbe.sourceLine };
                           publicGetters = @($exports | ForEach-Object { ConvertTo-SmalPublicField ([string]$_) });
                           staticSignatures = (Invoke-SmalOptionalRead 'module-static-public-signatures' { Get-SmalStaticPublicSignatures $module $exports }) }
                    })
                    $imported = @(foreach ($command in $commands) {
                        @{ name = (ConvertTo-SmalPublicField ([string]$command.Name)); commandType = [string]$command.CommandType;
                           moduleName = (ConvertTo-SmalPublicField ([string]$command.ModuleName));
                           moduleVersion = (ConvertTo-SmalPublicField ([string]$command.Module.Version));
                           modulePath = (ConvertTo-SmalPublicField ([string]$command.Module.Path));
                           signatures = (Invoke-SmalOptionalRead 'imported-command-public-signature' { Get-SmalImportedSignature $command }) }
                    })
                    return @{ status = 'metadata-only'; inventoryScope = 'PSModulePath-visible-list-available';
                        installedModuleReadStatus = $(if ($inventoryIssues.Count) { 'partial-read' } elseif ($modules.Count) { 'visible-public-candidates' } else { 'no-visible-public-match-not-absence' });
                        importedReadStatus = $(if ($commandIssues.Count) { 'partial-read' } elseif ($imported.Count) { 'imported-getters-observed' } else { 'no-imported-getters-not-absence' });
                        inventoryIssueCount = $inventoryIssues.Count; importedIssueCount = $commandIssues.Count;
                        inventoryIssues = @($inventoryIssues | ForEach-Object { @{ phase = 'installed-module-list-available'; errorType = (ConvertTo-SmalPublicField $_.Exception.GetType().FullName); errorCategory = [string]$_.CategoryInfo.Category } });
                        importedIssues = @($commandIssues | ForEach-Object { @{ phase = 'imported-getter-list'; errorType = (ConvertTo-SmalPublicField $_.Exception.GetType().FullName); errorCategory = [string]$_.CategoryInfo.Category } });
                        inventoryTraversalComplete = ($inventoryIssues.Count -eq 0); importedReadComplete = ($commandIssues.Count -eq 0);
                        publicExportReadsComplete = (@($modules | Where-Object { $_.publicExportsRead.status -cne 'complete' }).Count -eq 0);
                        modules = $modules; importedGetters = $imported;
                        getterInvocationPerformed = $false; moduleImportPerformed = $false;
                        signaturesCompleteForInvocation = $false; readinessFactsComplete = $false;
                        imageState = 'not-observed'; allocationOwnershipState = 'not-observed' }
                }
                function Get-SmalFoundationSupplement([string]$ExpectedName) {
                    if ($env:COMPUTERNAME -cne $ExpectedName) { throw 'Supplement identity differs' }
                    @{ status = 'optional-read-projections'; readinessFactsComplete = $false;
                       mocMetadata = (Invoke-SmalOptionalRead 'moc-public-metadata' { Get-SmalMocPublicMetadata });
                       nestedVmDisks = (Invoke-SmalOptionalRead 'nested-vm-disk-metadata' {
                           @(Get-VM | ForEach-Object {
                               $nested = $_
                               @{ name = (ConvertTo-SmalPublicField ([string]$nested.Name)); id = [string]$nested.Id;
                                  state = [string]$nested.State; cpu = [int]$nested.ProcessorCount;
                                  memoryBytes = [long]$nested.MemoryAssigned; startupMemoryBytes = [long]$nested.MemoryStartup;
                                  disks = (Invoke-SmalOptionalRead 'nested-vm-attached-vhd-metadata' {
                                      @(Get-VMHardDiskDrive -VM $nested | ForEach-Object {
                                          $disk = Get-VHD -Path $_.Path
                                          @{ path = (ConvertTo-SmalPublicField ([string]$_.Path)); id = [string]$disk.DiskIdentifier;
                                             maximumBytes = [long]$disk.Size; occupiedBytes = [long]$disk.FileSize; type = [string]$disk.VhdType }
                                      })
                                  }) }
                           })
                       });
                       routes = (Invoke-SmalOptionalRead 'guest-selected-route-metadata' {
                           @(foreach ($destination in @('10.64.0.100','10.64.0.180')) {
                               @{ destination = $destination; rows = @(Find-NetRoute -RemoteIPAddress $destination | ForEach-Object {
                                   @{ interfaceIndex = [int]$_.InterfaceIndex; interfaceAlias = (ConvertTo-SmalPublicField ([string]$_.InterfaceAlias));
                                      ipAddress = [string]$_.IPAddress; destinationPrefix = [string]$_.DestinationPrefix;
                                      nextHop = [string]$_.NextHop; routeMetric = [int]$_.RouteMetric }
                               }) }
                           })
                       }) }
                }
                Get-SmalFoundationSupplement $ExpectedName
            }
        } catch {
            $foundation = @{ status = 'failed'; phase = 'optional-guest-supplement'; readinessFactsComplete = $false;
                errorCategory = [string]$_.CategoryInfo.Category; sourceLine = [int]$_.InvocationInfo.ScriptLineNumber }
        }
        $profile = @{ status = 'unavailable' }
        try { $profile = @{ status = 'complete'; cpu = [int]$vm.ProcessorCount; startupMemoryBytes = [long]$vm.MemoryStartup;
                dynamicMemory = [bool](Get-VMMemory -VM $vm).DynamicMemoryEnabled } }
        catch { $profile = @{ status = 'failed'; phase = 'optional-host-guest-profile'; errorCategory = [string]$_.CategoryInfo.Category } }
        @{ name = $vm.Name; vmId = $vm.Id.ToString(); state = [string]$vm.State; guest = $guest;
           foundationSupplement = $foundation; foundationHostProfile = $profile }
    } finally { if ($session) { Remove-PSSession $session }; $secure.Dispose() }
})
$phase = 'outer-storage-inspection'
$base = @{ atUtc = [datetime]::UtcNow.ToString('o'); observationStatus = 'complete-read-only'; nodes = $nodes; outerPool = @(Get-StoragePool -FriendlyName LocalBoxPool | ForEach-Object { @{ uniqueId = $_.UniqueId; health = $_.HealthStatus.ToString(); memberCount = @($_ | Get-PhysicalDisk).Count } });
   volumes = @(Get-Volume | Where-Object DriveLetter -In @('C','V','W','X') | ForEach-Object { @{ letter = [string]$_.DriveLetter; uniqueId = $_.UniqueId; size = $_.Size; free = $_.SizeRemaining; health = $_.HealthStatus.ToString() } });
   credentialsReset = $false; mutationPerformed = $false; platformReadinessVerified = $false }
try {
    $base.foundationOuter = @{ status = 'complete'; cpu = [int](Get-VMHost).LogicalProcessorCount;
        memoryBytes = [long](Get-VMHost).MemoryCapacity;
        guests = @(Get-VM | ForEach-Object { @{ id = [string][guid]$_.Id;
            cpu = [int]$_.ProcessorCount; startupMemoryBytes = [long]$_.MemoryStartup; state = [string]$_.State } }) }
} catch { $base.foundationOuter = @{ status = 'failed'; phase = 'optional-outer-profile'; errorCategory = [string]$_.CategoryInfo.Category } }
$base.foundationAdmission = @{ readinessFactsComplete = $false; imageState = 'not-observed'; allocationOwnershipState = 'not-observed' }
$base | ConvertTo-Json -Depth 32 -Compress
} catch {
    # Never emit raw exception messages, command arguments or credential objects.
    @{ observationStatus = 'failed-safe-diagnostic'; phase = $phase; errorType = $_.Exception.GetType().Name;
       errorCategory = [string]$_.CategoryInfo.Category; sourceLine = $_.InvocationInfo.ScriptLineNumber;
       credentialsReset = $false; mutationPerformed = $false; platformReadinessVerified = $false } | ConvertTo-Json -Compress
}
