# Explicit NODE01 vendor-client runtime read. Never called by the metadata observer.
$ErrorActionPreference='Stop'
$phase='host-binding';$session=$null;$secure=$null
try {
    if ($env:COMPUTERNAME -cne 'LocalBox-Client') {throw 'Unexpected outer host'}
    $vm=Get-VM -Id '3adff629-2f67-449b-ab32-8a8748c46f34'
    if ($vm.Name -cne 'LB-NODE01' -or [string]$vm.State -cne 'Running') {throw 'Exact running NODE01 required'}
    $boot='C:\ProgramData\AzureLocalBox\Bootstrap\guest-bootstrap-20261028-01'
    $bundle=Get-Content (Join-Path $boot 'bundle.json') -Raw|ConvertFrom-Json
    $entry=@($bundle.files|Where-Object name -CEQ 'smal-guest-secret-functions.ps1');$helper=Join-Path $boot 'smal-guest-secret-functions.ps1'
    if ($entry.Count -ne 1 -or (Get-FileHash $helper).Hash -cne $entry[0].sha256) {throw 'Existing protected helper differs'}
    . $helper
    $store='C:\ProgramData\AzureLocalBox\Bootstrap\cluster-prereqs-20261028-01\secrets'
    $bindings=Get-Content 'C:\ProgramData\AzureLocalBox\Bootstrap\cluster-prereqs-20261028-01\credential-bindings.json' -Raw|ConvertFrom-Json
    $binding=$bindings.nodes.'LB-NODE01'
    if ($binding.vmId -ine $vm.Id.ToString() -or $binding.role -cne 'cluster-node-admin' -or $binding.secretDirectory -cne $store -or $binding.loginVerified -ne $true) {throw 'Existing NODE01 binding differs'}
    $secure=Read-LabGuestSecureSecret -SecretDirectory $store -Role 'cluster-node-admin'
    $phase='protected-session'
    $session=New-PSSession -VMId $vm.Id -Credential ([pscredential]::new('LB-NODE01\ASBuiltInAdmin',$secure)) -ErrorAction Stop
    $phase='vendor-client-read'
    $runtime={
        $ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
        $phase='guest-identity';$privateRoot=$null;$privateReady=$false;$calls=@();$pins=@()
        function Digest([byte[]]$Bytes) {
            $h=[Security.Cryptography.SHA256]::Create()
            try {[BitConverter]::ToString($h.ComputeHash($Bytes)).Replace('-','').ToLowerInvariant()} finally {$h.Dispose()}
        }
        function SafeValue($Value) {
            if ($null -eq $Value) {return @{status='not-reported'}}
            if ($Value -is [bool] -or $Value -is [byte] -or $Value -is [int16] -or $Value -is [uint16] -or $Value -is [int32] -or $Value -is [uint32] -or $Value -is [int64] -or $Value -is [uint64]) {return @{status='reported';value=$Value;type=$Value.GetType().FullName}}
            if ($Value -isnot [string] -and $Value -isnot [guid] -and $Value -isnot [enum]) {return @{status='unsupported-shape';type=$Value.GetType().FullName}}
            $text=[string]$Value
            if ($text.Length -gt 1024 -or $text -match '-----BEGIN|\beyJ[A-Za-z0-9_-]{15,}\.|(?i:password|access_token|refresh_token)|://|\?') {return @{status='withheld';sha256=(Digest ([Text.Encoding]::UTF8.GetBytes($text)))}}
            @{status='reported';value=$text;type=$Value.GetType().FullName}
        }
        function ProjectItem($Item) {
            # Fixed management fields only. Missing fields are not absence/zero evidence.
            $paths=@('id','name','type','location','group','state','provisioningState','path','imagePath','containerName','containerId','storageContainerId','version','imageVersion','kubernetesVersion','osType','osSku','architecture','size','sizeBytes','sizeInMB','sizeInGB','virtualSize','virtualSizeBytes','diskSizeBytes','diskSizeGB','properties.id','properties.name','properties.path','properties.imagePath','properties.provisioningState','properties.size','properties.sizeBytes','properties.sizeInMB','properties.sizeInGB','properties.virtualSizeBytes','properties.containerId','status.state','status.provisioningState','storageProfile.osDiskImage.sizeInMB','version.properties.storageProfile.osDiskImage.sizeInMB')
            $fields=@{};$missing=@()
            foreach($path in $paths) {
                $value=$Item;$present=$true
                foreach($part in $path.Split('.')) {
                    if ($null -eq $value -or $null -eq $value.PSObject.Properties[$part]) {$present=$false;break}
                    $value=$value.PSObject.Properties[$part].Value
                }
                if ($present) {$fields[$path]=SafeValue $value} else {$missing+= $path}
            }
            $unreported=@($fields.Values|Where-Object {$_.status -cne 'reported'}).Count
            @{fields=$fields;missingFields=$missing;withheldOrUnsupportedFieldCount=$unreported;allRequestedFieldsReported=($missing.Count -eq 0 -and $unreported -eq 0);imageOrCapacityAdmitted=$false}
        }
        function SaveCapture([string]$Name,$records,$failure) {
            if ($null -eq $failure) {$failure=@($records|Where-Object {$_ -is [Management.Automation.ErrorRecord]})|Select-Object -First 1}
            $text=($records|Out-String -Width 4096)
            if ($null -ne $failure) {$text+=[Environment]::NewLine+$failure.ToString()}
            $bytes=[Text.Encoding]::UTF8.GetBytes($text)
            $log=Join-Path $privateRoot ($Name+'.txt')
            # Node-local protected diagnostic only. Never return raw vendor streams.
            $file=[IO.File]::Open($log,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
            try {$file.Write($bytes,0,[Math]::Min($bytes.Length,1048576))} finally {$file.Dispose()}
            $diagnostic=@{path=$log;fullStreamSha256=(Digest $bytes);bytes=$bytes.Length;retainedBytes=[Math]::Min($bytes.Length,1048576);truncated=($bytes.Length -gt 1048576)}
            if ($null -ne $failure) {
                $original=[Text.Encoding]::UTF8.GetBytes($failure.ToString());$originalPath=Join-Path $privateRoot ($Name+'-original-failure.txt')
                $s=[IO.File]::Open($originalPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
                try{$s.Write($original,0,[Math]::Min($original.Length,1048576))}finally{$s.Dispose()}
                return @{status='failed';phase=$Name;errorType=(SafeValue $failure.Exception.GetType().FullName);errorCategory=[string]$failure.CategoryInfo.Category;diagnostic=$diagnostic;originalFailure=@{path=$originalPath;sha256=(Digest $original);bytes=$original.Length;truncated=($original.Length -gt 1048576)}}
            }
            $data=@($records|Where-Object {$_ -isnot [Management.Automation.InformationRecord] -and $_ -isnot [Management.Automation.WarningRecord] -and $_ -isnot [Management.Automation.VerboseRecord] -and $_ -isnot [Management.Automation.DebugRecord] -and $_ -isnot [Management.Automation.ErrorRecord]})
            @{status='complete';phase=$Name;data=$data;diagnostic=$diagnostic}
        }
        function ClientCall([string]$Name,[scriptblock]$Read) {
            $records=[Collections.Generic.List[object]]::new();$failure=$null
            try {& $Read *>&1|ForEach-Object {$records.Add($_)}} catch {$failure=$_}
            SaveCapture $Name $records $failure
        }
        function Items($Call) {
            $data=@($Call.data)
            if ($data.Count -eq 1 -and $null -ne $data[0].PSObject.Properties['value']) {$data=@($data[0].value)}
            if ($data.Count -gt 64 -or @($data|Where-Object {$_ -is [string]}).Count) {throw 'Unsupported or oversized vendor result shape'}
            return ,$data
        }
        try {
            if ($env:COMPUTERNAME -cne 'LB-NODE01') {throw 'Unexpected guest'}
            $admin=Get-LocalUser -Name ASBuiltInAdmin
            if (-not $admin.Enabled -or -not $admin.SID.Value.EndsWith('-500') -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne $admin.SID.Value) {throw 'Existing RID500 identity differs'}
            $phase='pins-before-import'
            $base='C:\Program Files\WindowsPowerShell\Modules\'
            $expected=@(
                @('Moc\1.2.161\Moc.psd1','b4c171acdf6bdaf86a6751396e27b52714af2d1410505d1f3412103cf5435c3f','AB172913A2960A224809EE8A0C371CD47A079B72'),
                @('Moc\1.2.161\Moc.psm1','b9dbda4ab8c0ce6c77d8fa219a153983114afc859f5bb10689f6f3cf71025b7f','AB172913A2960A224809EE8A0C371CD47A079B72'),
                @('Moc\1.2.161\Common.psm1','1c4ce70357820cb4c2d95f6ac9a51fa3e9067f9130714b6f77aeaa46cd97babb','AB172913A2960A224809EE8A0C371CD47A079B72'),
                @('DownloadSdk\1.1.149\DownloadSdk.psd1','167b5fef982f9cfb191ab208f0fa67263ed2c29ea9541d3ef369a763f2c12c39','AB172913A2960A224809EE8A0C371CD47A079B72'),
                @('DownloadSdk\1.1.149\DownloadSdk.psm1','b14eb2061006cdd47069772bd6ff1919dbf6425814c73de4e90d14153097cdbc','AB172913A2960A224809EE8A0C371CD47A079B72'),
                @('TraceProvider\1.0.156\TraceProvider.psd1','4e12356f2d70a3edd58fb40865ceb6308d90a78c10693e40c8914946502c984d','1D77A9B9E8FE2075D9AD15123257FB90DB0DA4A1'),
                @('TraceProvider\1.0.156\TraceProvider.psm1','11d66b33526c7be33f6a50f658e917546d7d2439bd9d9279fc35b374fd0d0b80','AB172913A2960A224809EE8A0C371CD47A079B72'))
            foreach($pin in $expected) {
                $path=$base+$pin[0];$directory=[IO.FileInfo]::new($path).Directory
                $ancestors=@();while($null -ne $directory){$ancestors=@($directory)+$ancestors;$directory=$directory.Parent}
                foreach($ancestor in $ancestors){$ancestor.Refresh();if(-not $ancestor.Exists -or ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Redirected public module ancestor'}}
                $info=[IO.FileInfo]::new($path);if(-not $info.Exists -or $info.Length -gt 2097152 -or ($info.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Public module file outside bound'}
                if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ine $pin[1]) {throw 'Observed public module hash differs'}
                $signature=Get-AuthenticodeSignature -FilePath $path
                if ([string]$signature.Status -cne 'Valid' -or $signature.SignerCertificate.Thumbprint -ine $pin[2]) {throw 'Observed public signer differs'}
                $pins+=@{path=$path;sha256=$pin[1];signature='Valid';signerThumbprint=$pin[2]}
            }
            if (@(Get-Module -Name Moc).Count) {throw 'Unexpected pre-imported Moc module'}
            $privateRoot='C:\ProgramData\AzureLocalBox\MocRead-20261109-02'
            if (-not (Test-Path -LiteralPath $privateRoot) -or $PSCommandPath -ine (Join-Path $privateRoot 'client-read.ps1')) {throw 'Expected protected fixed client process required'}
            $begin=[IO.File]::Open((Join-Path $privateRoot 'client-began'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read);$begin.Dispose()
            $privateReady=$true
            $phase='import'
            # Import in this remote script scope, not a short-lived capture-function scope.
            $records=[Collections.Generic.List[object]]::new();$failure=$null
            try {Import-Module -Name 'C:\Program Files\WindowsPowerShell\Modules\Moc\1.2.161\Moc.psd1' -Scope Local -PassThru -ErrorAction Stop *>&1|ForEach-Object {$records.Add($_)}} catch {$failure=$_}
            $call=SaveCapture 'import' $records $failure
            $calls+=@{phase=$phase;status=$call.status;diagnostic=$call.diagnostic}
            if ($call.status -cne 'complete') {return @{status='failed';failure=$call;pins=$pins;calls=$calls}}
            $loaded=@(Get-Module -Name Moc)
            if ($loaded.Count -ne 1 -or [string]$loaded[0].Version -cne '1.2.161' -or [string]$loaded[0].Guid -ine 'f6cfb7b2-99e9-47f7-8000-7390756ee89b') {throw 'Imported Moc identity differs'}
            $phase='locations'
            $call=ClientCall 'locations' {Get-MocLocation -timeoutSeconds 20 -ErrorAction Stop}
            if ($call.status -cne 'complete') {return @{status='failed';failure=$call;pins=$pins;calls=$calls}}
            $locations=Items $call
            $calls+=@{phase=$phase;status='complete';count=$locations.Count;items=@($locations|ForEach-Object {ProjectItem $_});diagnostic=$call.diagnostic}
            if ($locations.Count -ne 1 -or $null -eq $locations[0].PSObject.Properties['name'] -or $locations[0].name -isnot [string] -or $locations[0].name -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$') {return @{status='scope-incomplete-stop';reason='Unique actual lab location name not established';pins=$pins;calls=$calls}}
            $location=$locations[0].name
            foreach($name in @('gallery-images','containers','groups')) {
                $phase=$name
                $call=switch($name){
                    'gallery-images' {ClientCall $name {Get-MocGalleryImage -location $location -timeoutSeconds 20 -ErrorAction Stop}}
                    'containers' {ClientCall $name {Get-MocContainer -location $location -timeoutSeconds 20 -ErrorAction Stop}}
                    'groups' {ClientCall $name {Get-MocGroup -location $location -timeoutSeconds 20 -ErrorAction Stop}}
                }
                if ($call.status -cne 'complete') {return @{status='failed';failure=$call;pins=$pins;calls=$calls}}
                $items=Items $call
                $calls+=@{phase=$phase;status='complete';count=$items.Count;items=@($items|ForEach-Object {ProjectItem $_});diagnostic=$call.diagnostic}
            }
            @{status='complete';atUtc=[DateTime]::UtcNow.ToString('o');location=(SafeValue $location);pins=$pins;calls=$calls;
              runtimePermissionUsed='existing-client-auth-cache-log-environment-and-idempotent-read-retry';resourceWritesRequested=$false;
              imageAllocationOrCapacityAdmitted=$false;rawStreamsExported=$false}
        } catch {
            $failure=@{phase=$phase;errorType=(SafeValue $_.Exception.GetType().FullName);errorCategory=[string]$_.CategoryInfo.Category;sourceLine=[int]$_.InvocationInfo.ScriptLineNumber}
            if ($privateReady -and (Test-Path -LiteralPath $privateRoot)) {
                $bytes=[Text.Encoding]::UTF8.GetBytes($_.ToString());$file=Join-Path $privateRoot 'original-failure.txt'
                $s=[IO.File]::Open($file,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
                try{$s.Write($bytes,0,[Math]::Min($bytes.Length,1048576))}finally{$s.Dispose()}
                $failure.privateOriginal=$file;$failure.sha256=Digest $bytes
            }
            @{status='failed';failure=$failure;pins=$pins;calls=$calls;rawStreamsExported=$false}
        }
    }
    # One fixed child, not a general dispatcher: catches vendor Out-Default/console output.
    $clientSource="function Invoke-FixedMocRead {`n"+$runtime.ToString()+"`n}`n"+
        '$safe=Invoke-FixedMocRead;[IO.File]::WriteAllText(''C:\ProgramData\AzureLocalBox\MocRead-20261109-02\result.json'',($safe|ConvertTo-Json -Depth 20 -Compress),[Text.UTF8Encoding]::new($false))'
    $result=Invoke-Command -Session $session -ArgumentList $clientSource -ErrorAction Stop -ScriptBlock {
        param([string]$ClientSource)
        $ErrorActionPreference='Stop'
        if ($env:COMPUTERNAME -cne 'LB-NODE01' -or -not [Security.Principal.WindowsIdentity]::GetCurrent().User.Value.EndsWith('-500')) {throw 'Expected NODE01/RID500 client context'}
        function Read-OriginalMocState([string]$Root) {
            try {
                $scriptPath=Join-Path $Root 'client-read.ps1'
                $parent=Get-Item -LiteralPath ([IO.Path]::GetDirectoryName($Root)) -Force -ErrorAction Stop
                if ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) {throw 'Original operation parent redirected'}
                $exists=Test-Path -LiteralPath $Root -ErrorAction Stop;$entries=@();$files=@{}
                if ($exists) {
                    $directory=Get-Item -LiteralPath $Root -Force -ErrorAction Stop
                    if (-not $directory.PSIsContainer -or ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint)) {throw 'Original operation root is not a plain directory'}
                    $entries=@(Get-ChildItem -LiteralPath $Root -Force -ErrorAction Stop)
                }
                $record=$null;$resultStatus='not-reported'
                foreach($name in @('client-read.ps1','process.json','result.json')) {
                    $path=Join-Path $Root $name;$item=@($entries|Where-Object Name -CEQ $name)
                    $files[$name]=@{exists=($item.Count -eq 1)}
                    if (-not $item.Count) {continue}
                    if ($item.Count -ne 1 -or $item[0].PSIsContainer -or ($item[0].Attributes -band [IO.FileAttributes]::ReparsePoint)) {throw 'Original state entry redirected or invalid'}
                    $files[$name].bytes=$item[0].Length;$files[$name].lastWriteUtc=$item[0].LastWriteTimeUtc.ToString('o')
                    if ($name -ceq 'process.json') {
                        if ($item[0].Length -gt 65536) {throw 'Original process record exceeds bound'}
                        $value=Get-Content -LiteralPath $path -Raw -ErrorAction Stop|ConvertFrom-Json
                        $record=@{status='unrecognised';pid=$null;sourceSha256=$null}
                        if ($value.status -cin @('running','exited','uncertain-client-still-running-do-not-retry')) {$record.status=$value.status}
                        if (($value.pid -is [int] -or $value.pid -is [long]) -and $value.pid -gt 0 -and $value.pid -le [int]::MaxValue) {$record.pid=$value.pid}
                        if ($value.sourceSha256 -is [string] -and $value.sourceSha256 -cmatch '^[a-f0-9]{64}$') {$record.sourceSha256=$value.sourceSha256}
                    }
                    if ($name -ceq 'result.json') {
                        if ($item[0].Length -gt 1048576) {throw 'Original safe result exceeds bound'}
                        $value=Get-Content -LiteralPath $path -Raw -ErrorAction Stop|ConvertFrom-Json
                        if ($value.status -cin @('complete','failed','scope-incomplete-stop')) {$resultStatus=$value.status}
                    }
                }
                $processes=@(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction Stop)
                $unknown=@($processes|Where-Object {[string]::IsNullOrWhiteSpace($_.CommandLine)}).Count
                $matches=@($processes|Where-Object {$_.CommandLine -is [string] -and $_.CommandLine.IndexOf($scriptPath,[StringComparison]::OrdinalIgnoreCase) -ge 0}|ForEach-Object {
                    @{pid=$_.ProcessId;creationUtc=$(if($_.CreationDate -is [datetime]){$_.CreationDate.ToUniversalTime().ToString('o')}else{'not-reported'});matchesOriginalScript=$true}
                })
                # Published -01 writes the script before starting the process and never deletes it.
                # A returned/dead process alone is deliberately not independent settlement.
                $unstarted=$entries.Count -eq 0 -and $matches.Count -eq 0 -and $unknown -eq 0
                @{readComplete=$true;observedAtUtc=[DateTime]::UtcNow.ToString('o');root=$Root;rootExists=$exists;entryCount=$entries.Count;files=$files;processRecord=$record;safeResultStatus=$resultStatus;
                  matchingProcesses=$matches;unreadablePowerShellCommandLineCount=$unknown;provedPrelaunchUnstarted=$unstarted;independentlySettled=$false;
                  requiresIndependentSettlement=(-not $unstarted);rawCommandLinesExported=$false}
            } catch { @{readComplete=$false;root=$Root;provedPrelaunchUnstarted=$false;independentlySettled=$false;requiresIndependentSettlement=$true;errorType=$_.Exception.GetType().FullName;errorCategory=[string]$_.CategoryInfo.Category} }
        }
        function New-ProtectedMocDirectory([string]$Root) {
            if (Test-Path -LiteralPath $Root) {throw 'Fresh diagnostic root already exists; no replay'}
            $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
            if (-not $sid.Value.EndsWith('-500')) {throw 'Current RID500 identity required'}
            $acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetOwner($sid);$acl.SetAccessRuleProtection($true,$false)
            foreach($principal in @($sid,[Security.Principal.SecurityIdentifier]::new('S-1-5-18'),[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
                $rule=[Security.AccessControl.FileSystemAccessRule]::new($principal,[Security.AccessControl.FileSystemRights]::FullControl,
                    ([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit),[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
                $acl.AddAccessRule($rule)
            }
            $null=New-Item $Root -ItemType Directory -ErrorAction Stop
            Set-Acl -LiteralPath $Root -AclObject $acl -ErrorAction Stop
            if (-not (Get-Acl -LiteralPath $Root).AreAccessRulesProtected) {throw 'Node-local diagnostic DACL is not protected'}
        }
        $original=Read-OriginalMocState 'C:\ProgramData\AzureLocalBox\MocRead-20261109-01'
        if ($original.readComplete -ne $true -or $original.provedPrelaunchUnstarted -ne $true) {return @{status='blocked-original-reconciliation-required';original=$original;retryAllowed=$false}}
        $root='C:\ProgramData\AzureLocalBox\MocRead-20261109-02'
        if (Test-Path -LiteralPath $root) {return @{status='blocked-second-root-already-exists';original=$original;secondRoot=(Read-OriginalMocState $root);retryAllowed=$false}}
        New-ProtectedMocDirectory $root
        $script=Join-Path $root 'client-read.ps1';[IO.File]::WriteAllText($script,$ClientSource,[Text.UTF8Encoding]::new($false))
        $sourceSha=(Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
        $process=Start-Process -FilePath powershell.exe -ArgumentList @('-NoLogo','-NoProfile','-NonInteractive','-File',$script) -RedirectStandardOutput (Join-Path $root 'client.stdout') -RedirectStandardError (Join-Path $root 'client.stderr') -PassThru
        $record=@{status='running';pid=$process.Id;processStartedUtc=$process.StartTime.ToUniversalTime().ToString('o');sourceSha256=$sourceSha;retryAllowed=$false;privateRoot=$root;original=$original}
        [IO.File]::WriteAllText((Join-Path $root 'process.json'),($record|ConvertTo-Json -Compress))
        if (-not $process.WaitForExit(75000)) {
            $record.status='uncertain-client-still-running-do-not-retry'
            [IO.File]::WriteAllText((Join-Path $root 'process.json'),($record|ConvertTo-Json -Compress));return $record
        }
        $process.Refresh();$record.status='exited';$record.exitCode=$process.ExitCode
        [IO.File]::WriteAllText((Join-Path $root 'process.json'),($record|ConvertTo-Json -Compress))
        $path=Join-Path $root 'result.json'
        if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -gt 1048576) {return @{status='failed-private-client-result-unavailable';original=$original;process=$record;rawStreamsExported=$false}}
        @{status='client-result';original=$original;process=$record;result=(Get-Content -LiteralPath $path -Raw|ConvertFrom-Json);rawStreamsExported=$false}
    }
    @{node='LB-NODE01';vmId=$vm.Id.ToString();result=$result;atUtc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 24 -Compress
} catch {
    @{status='failed';phase=$phase;errorType=$_.Exception.GetType().FullName;errorCategory=[string]$_.CategoryInfo.Category;rawStreamsExported=$false}|ConvertTo-Json -Compress
} finally {
    if ($session) {Remove-PSSession $session}
    if ($secure) {$secure.Dispose()}
}
