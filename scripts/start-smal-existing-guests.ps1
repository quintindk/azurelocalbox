# Restore only the four approved existing guests after an outer-host shutdown.
# No registration, marker deletion, VM reconfiguration or bootstrap invocation.
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -cne 'LocalBox-Client') { throw 'Unexpected outer host' }
$capacityMutex = [Threading.Mutex]::new($false, 'Global\AzureLocalBoxComputeCapacityR2')
$capacityMutexHeld = $false
try {
    try { $capacityMutexHeld = $capacityMutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] {
        $capacityMutexHeld = $true
        throw 'Abandoned capacity mutex. Inspect original operation evidence before startup.'
    }
    if (-not $capacityMutexHeld) { throw 'Remote capacity dispatcher, worker or startup is active. No guest start.' }
    $capacityGate = $null
    $legacyCapacityRoot = 'C:\ProgramData\AzureLocalBox\ComputeCapacity-20261108-01'
    if (Test-Path -LiteralPath $legacyCapacityRoot) {
        throw 'Retained remote legacy capacity history requires reviewed source and exact settlement before guest startup. No marker is changed.'
    }
    $capacityRoot = 'C:\ProgramData\AzureLocalBox\ComputeCapacity-R2-20261108-01'
    if (Test-Path -LiteralPath $capacityRoot) {
        throw 'Retained remote R2 history requires reviewed source and exact settlement before guest startup. No helper, grant or marker is changed.'
    }
    $profileRoot='C:\ProgramData\AzureLocalBox\FoundationProfile-20261109-01'
    if (Test-Path -LiteralPath $profileRoot) {
        $operation=Get-Content (Join-Path $profileRoot 'operation.json') -Raw|ConvertFrom-Json
        $closed=Get-Content (Join-Path $profileRoot 'completion.json') -Raw|ConvertFrom-Json
        if ($operation.operationId -cne 'smal-foundation-profile-20261109-01' -or $operation.active -ne $false -or $closed.planSha256 -cne $operation.planSha256 -or $closed.sourceCommit -cne $operation.sourceCommit -or $closed.allHealthyAndOk -ne $true -or $closed.noActiveStorageJobs -ne $true -or $closed.allOriginalOperationsReconciled -ne $true) { throw 'Rolling profile operation is not closed; no normal startup' }
        foreach($file in @(Get-ChildItem $profileRoot -Filter 'worker-*.state.json' -File)) {
            $s=Get-Content $file.FullName -Raw|ConvertFrom-Json;$p=Get-Process -Id $s.pid -ErrorAction SilentlyContinue
            if ($s.phase -cne 'returned' -or ($p -and $p.StartTime.ToUniversalTime().ToString('o') -ceq $s.processStartedUtc)) { throw 'Original rolling worker unresolved; no normal startup' }
        }
        foreach($vm in @(Get-VM)) { $p=$closed.finalProfiles.PSObject.Properties[$vm.Name].Value;if ($null -eq $p -or $p.cpu -ne $vm.ProcessorCount -or $p.memory -ne $vm.MemoryStartup) { throw 'Completed rolling profiles drifted' } }
    }
    $profileRoot='C:\ProgramData\AzureLocalBox\FoundationProfile-20261110-02'
    if (Test-Path -LiteralPath $profileRoot) {
        $operation=Get-Content (Join-Path $profileRoot 'operation.json') -Raw|ConvertFrom-Json
        $closed=Get-Content (Join-Path $profileRoot 'completion.json') -Raw|ConvertFrom-Json
        if ($operation.operationId -cne 'smal-foundation-profile-20261110-02' -or $operation.active -ne $false -or $closed.planSha256 -cne $operation.planSha256 -or $closed.sourceCommit -cne $operation.sourceCommit -or $closed.allHealthyAndOk -ne $true -or $closed.noActiveStorageJobs -ne $true -or $closed.allOriginalOperationsReconciled -ne $true) { throw 'Rolling profile operation is not closed; no normal startup' }
        foreach($file in @(Get-ChildItem $profileRoot -Filter 'worker-*.state.json' -File)) {
            $s=Get-Content $file.FullName -Raw|ConvertFrom-Json;$p=Get-Process -Id $s.pid -ErrorAction SilentlyContinue
            if ($s.phase -cne 'returned' -or ($p -and $p.StartTime.ToUniversalTime().ToString('o') -ceq $s.processStartedUtc)) { throw 'Original rolling worker unresolved; no normal startup' }
        }
        foreach($vm in @(Get-VM)) { $p=$closed.finalProfiles.PSObject.Properties[$vm.Name].Value;if ($null -eq $p -or $p.cpu -ne $vm.ProcessorCount -or $p.memory -ne $vm.MemoryStartup) { throw 'Completed rolling profiles drifted' } }
    }
    $targets = @(
        @{ name = 'LB-DC01'; id = 'f94c71f1-6854-48b9-a9f1-8238c99366d0' },
        @{ name = 'LB-NODE01'; id = '3adff629-2f67-449b-ab32-8a8748c46f34' },
        @{ name = 'LB-NODE02'; id = '12a44e0c-cc08-4c4c-a812-fa0b56efdbc3' },
        @{ name = 'LB-NODE03'; id = '5b6eba15-fa82-4e12-9e45-5ffbcd48c8a9' }
    )
    # Validate every identity/state before starting any guest. Never reset a bad state.
    foreach ($target in $targets) {
        $vm = Get-VM -Id $target.id
        if ($vm.Name -cne $target.name -or $vm.State.ToString() -notin @('Off', 'Saved', 'Running')) { throw 'Exact approved guest identity or restorable state differs' }
    }
    $results = @(foreach ($target in $targets) {
        $vm = Get-VM -Id $target.id
        $before = $vm.State.ToString()
        if ($before -ne 'Running') {
            if ($capacityGate) { Set-CapacityStartupPhase $capacityGate 'rpc-pending' $vm.Id.ToString() }
            try { Start-VM -VM $vm -ErrorAction Stop }
            finally { if ($capacityGate) { Set-CapacityStartupPhase $capacityGate 'rpc-returned' $vm.Id.ToString() } }
        }
        $vm = Get-VM -Id $target.id
        if ($vm.Name -cne $target.name -or $vm.State.ToString() -ne 'Running') { throw 'Guest did not reach Running' }
        @{ name = $vm.Name; id = $vm.Id.ToString(); before = $before; after = $vm.State.ToString(); startRequested = ($before -ne 'Running'); heartbeatReady = $false }
    })
    # Heartbeat is an OS-liveness check, not AD/Arc/cluster/application acceptance.
    $deadline = [datetime]::UtcNow.AddSeconds(240)
    do {
        foreach ($row in $results) {
            $vm = Get-VM -Id $row.id
            if ($vm.Name -cne $row.name -or $vm.State.ToString() -ne 'Running') { throw 'Guest stopped or identity changed during startup' }
            $row.heartbeatReady = $vm.Heartbeat.ToString() -in @('OkApplicationsUnknown', 'OkApplicationsHealthy')
        }
        if (@($results | Where-Object { -not $_.heartbeatReady }).Count -eq 0) { break }
        if ([datetime]::UtcNow -ge $deadline) { throw 'Guest heartbeat readiness timed out. Inspect before retrying.' }
        Start-Sleep -Seconds 5
    } while ($true)
    if ($capacityGate) { Set-CapacityStartupPhase $capacityGate 'returned' }
    @{ atUtc = [datetime]::UtcNow.ToString('o'); guests = $results; capacityInterlock = $(if ($capacityGate) { @{ key = $capacityGate.key; planSha256 = $capacityGate.planSha256; phase = $capacityGate.phase } } else { $null }); registrationInvoked = $false; registrationMarkersChanged = $false; guestOsReadinessVerified = $false; guestHeartbeatVerified = $true } | ConvertTo-Json -Depth 4 -Compress
} finally {
    if ($capacityMutexHeld) { $capacityMutex.ReleaseMutex() }
    $capacityMutex.Dispose()
}
