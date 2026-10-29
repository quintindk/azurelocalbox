# Read-only current four-guest topology, live MACs, exact storage and bootstrap facts.
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -cne 'LocalBox-Client') { throw 'Unexpected host' }
$targets = @(
    @{ name = 'LB-NODE01'; id = '3adff629-2f67-449b-ab32-8a8748c46f34' },
    @{ name = 'LB-NODE02'; id = '12a44e0c-cc08-4c4c-a812-fa0b56efdbc3' },
    @{ name = 'LB-NODE03'; id = '5b6eba15-fa82-4e12-9e45-5ffbcd48c8a9' }
)
$boot = 'C:\ProgramData\AzureLocalBox\Bootstrap\guest-bootstrap-20261028-01'
$bundle = Get-Content (Join-Path $boot 'bundle.json') -Raw | ConvertFrom-Json
$entry = @($bundle.files | Where-Object name -CEQ 'smal-guest-secret-functions.ps1')
$helper = Join-Path $boot 'smal-guest-secret-functions.ps1'
if ($entry.Count -ne 1 -or (Get-FileHash $helper).Hash -cne $entry[0].sha256) { throw 'Secret helper differs' }
. $helper
$store = 'C:\ProgramData\AzureLocalBox\Bootstrap\cluster-prereqs-20261028-01\secrets'
$bindings = Get-Content 'C:\ProgramData\AzureLocalBox\Bootstrap\cluster-prereqs-20261028-01\credential-bindings.json' -Raw | ConvertFrom-Json
$nodes = @(foreach ($target in $targets) {
    $vm = Get-VM -Id $target.id; $binding = $bindings.nodes.PSObject.Properties[$target.name].Value
    if ($vm.Name -cne $target.name -or $vm.State.ToString() -ne 'Running' -or $vm.MemoryStartup -ne 64GB -or $vm.ProcessorCount -ne 8 -or $binding.vmId -ine $target.id -or $binding.loginVerified -ne $true -or $binding.secretDirectory -cne $store -or $binding.role -cne 'cluster-node-admin') { throw 'Exact current VM profile/binding differs' }
    $secure = Read-LabGuestSecureSecret -SecretDirectory $store -Role 'cluster-node-admin'; $session = $null
    try {
        $session = New-PSSession -VMId $vm.Id -Credential ([pscredential]::new(($vm.Name + '\Administrator'), $secure)) -ErrorAction Stop
        $guest = Invoke-Command -Session $session -ErrorAction Stop -ScriptBlock {
            $ErrorActionPreference = 'Stop'; $os = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
            $cmd = Get-Command Invoke-AzStackHciArcInitialization -ErrorAction SilentlyContinue
            $bootstrap = $null; $bootstrapError = $null
            try { $bootstrap = [string](Get-ArcBootstrapStatus).Response.Status } catch { $bootstrapError = $_.Exception.GetType().Name }
            @{ name = $env:COMPUTERNAME; build = ($os.CurrentBuild + '.' + $os.UBR); domainRole = (Get-CimInstance Win32_ComputerSystem).DomainRole;
               adapters = @(Get-NetAdapter | Select-Object Name,MacAddress,Status); ipv4 = @(Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,IPAddress,PrefixLength);
               disks = @(Get-Disk | ForEach-Object { @{ uniqueId = $_.UniqueId; size = $_.Size; style = $_.PartitionStyle.ToString(); isBoot = $_.IsBoot; isSystem = $_.IsSystem } });
               nonPrimordialPoolCount = @(Get-StoragePool | Where-Object IsPrimordial -EQ $false).Count;
               bootstrapStatus = $bootstrap; bootstrapReadErrorType = $bootstrapError;
               bootstrapCommand = @{ available = [bool]$cmd; version = $(if ($cmd.Module) { $cmd.Module.Version.ToString() } else { $null }); sha256 = $(if ($cmd.Module.Path) { (Get-FileHash $cmd.Module.Path).Hash } else { $null }) };
               defenderEnabled = (Get-MpComputerStatus).RealTimeProtectionEnabled; firewallEnabled = @(Get-NetFirewallProfile | Where-Object Enabled -NE $true).Count -eq 0;
               platformPaths = @(@{ fqdn = 'kv-lbox-weu-4766ea.vault.azure.net'; ip = '10.200.17.11' }, @{ fqdn = 'stlboxdiagweu4766ea.blob.core.windows.net'; ip = '10.200.17.9' }, @{ fqdn = 'stlboxwitweu4766ea.blob.core.windows.net'; ip = '10.200.17.10' } | ForEach-Object {
                   $row = @{ fqdn = $_.fqdn; expectedIp = $_.ip; addresses = @(); tlsHttpStatus = $null }
                   $row.addresses = @(Resolve-DnsName -Name $_.fqdn -Type A -DnsOnly -QuickTimeout -ErrorAction Stop | Where-Object IPAddress | ForEach-Object IPAddress)
                   if ($row.addresses.Count -ne 1 -or $row.addresses[0] -cne $row.expectedIp) { throw 'Platform private DNS differs' }
                   $request = [Net.HttpWebRequest]::Create('https://' + $_.fqdn + '/'); $request.Method = 'HEAD'; $request.AllowAutoRedirect = $false; $request.UseDefaultCredentials = $false; $request.Timeout = 15000
                   try { $response = $request.GetResponse(); try { $row.tlsHttpStatus = [int]$response.StatusCode } finally { $response.Close() } }
                   catch [Net.WebException] { if ($_.Exception.Response) { $row.tlsHttpStatus = [int]$_.Exception.Response.StatusCode; $_.Exception.Response.Close() } }
                   if ($null -eq $row.tlsHttpStatus) { throw 'Normal hostname TLS/HTTP path not verified' }; $row
               }) }
        }
        @{ name = $vm.Name; vmId = $vm.Id.ToString(); state = $vm.State.ToString(); memoryBytes = $vm.MemoryStartup; processors = $vm.ProcessorCount;
           hostAdapters = @(Get-VMNetworkAdapter -VM $vm | Select-Object Name,MacAddress,SwitchId);
           hostDisks = @(Get-VMHardDiskDrive -VM $vm | ForEach-Object { $vhd = Get-VHD -Path $_.Path; @{ path = $_.Path; lun = $_.ControllerLocation; diskId = $vhd.DiskIdentifier.ToString(); size = $vhd.Size; parentPath = $vhd.ParentPath } }); guest = $guest }
    } finally { if ($session) { Remove-PSSession $session }; $secure.Dispose() }
})
@{ atUtc = [datetime]::UtcNow.ToString('o'); nodes = $nodes; guests = @(Get-VM | ForEach-Object { @{ name = $_.Name; id = $_.Id.ToString(); state = $_.State.ToString(); memoryBytes = $_.MemoryStartup; processors = $_.ProcessorCount } });
   volumes = @(Get-Volume | Where-Object DriveLetter -In @('C','V','W') | ForEach-Object { @{ letter = [string]$_.DriveLetter; size = $_.Size; free = $_.SizeRemaining; health = $_.HealthStatus.ToString(); uniqueId = $_.UniqueId } });
   mutationPerformed = $false; registrationInvoked = $false; platformReadinessVerified = $false } | ConvertTo-Json -Depth 13 -Compress
