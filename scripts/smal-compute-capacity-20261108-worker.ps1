# R2 detached worker template. Renderer prefixes exact sealed plan/stage/source and common helpers.
$ErrorActionPreference = 'Stop'
$root = 'C:\ProgramData\AzureLocalBox\ComputeCapacity-R2-20261108-01'
$entry = $plan.transitionContract.stages.PSObject.Properties[$stage].Value
$statePath = Join-Path $root ('worker-' + $stage + '.state.json')
$state = @{ operationId = $plan.operationId; planSha256 = $planSha; sourceCommit = $sourceCommit; stage = $stage; key = $effectKey
    phase = 'preflight'; pid = $PID; processStartedUtc = (Get-Process -Id $PID).StartTime.ToUniversalTime().ToString('o')
    sourceSha256 = (Get-FileHash -LiteralPath $PSCommandPath).Hash; sequence = 0; rpcInvoked = $false; outcome = 'unknown' }
function Save-R2Worker([string]$phase) {
    $state.sequence++; $state.phase = $phase; $state.atUtc = [datetime]::UtcNow.ToString('o')
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($state | ConvertTo-Json -Depth 25 -Compress))
    $event = Join-Path $root ('worker-' + $stage + '-event-' + $state.sequence + '.json')
    $stream = [IO.File]::Open($event, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    $tmp = $statePath + '.' + [guid]::NewGuid().ToString('N')
    $stream = [IO.File]::Open($tmp, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    if (Test-Path $statePath) { [IO.File]::Replace($tmp, $statePath, $null) } else { [IO.File]::Move($tmp, $statePath) }
}
function Assert-R2Profiles($snapshot, $profiles, $states) {
    Assert-ComputeEqual $snapshot.hostStatic $plan.baseline.hostStatic 'Outer pool/network drift'
    Assert-ComputeEqual $snapshot.volumesStatic $plan.baseline.volumesStatic 'Outer volume drift'
    foreach ($g in $snapshot.guestsStatic) {
        $expected = $profiles.PSObject.Properties[$g.name].Value
        Assert-Compute ($expected.cpu -eq $g.cpu -and $expected.memory -eq $g.memory -and $states.PSObject.Properties[$g.name].Value -ceq $snapshot.states[$g.name]) 'Exact stage profile/state differs'
        $original = @($plan.baseline.guestsStatic | Where-Object name -CEQ $g.name)[0]
        $copy = @{}; foreach ($key in $g.Keys) { $copy[$key] = $g[$key] }
        $copy.cpu = $original.cpu; $copy.memory = $original.memory
        Assert-ComputeEqual $copy $original 'Non-profile guest/VHD/TPM/NIC drift'
    }
}
$mutex = [Threading.Mutex]::new($false, 'Global\AzureLocalBoxComputeCapacityR2')
$held = $false; $session = $null
try {
    $held = $mutex.WaitOne(10000)
    if (-not $held) { throw 'Remote worker mutex unavailable' }
    Save-R2Worker 'preflight'
    if ($env:COMPUTERNAME -cne 'LocalBox-Client' -or $plan.transitionContract.version -ne 2 -or $plan.executionApproval.parentGo -ne $true -or $entry.key -cne $effectKey) { throw 'Exact approved worker context differs' }
    $clusterRead = $entry.healthProfile -cne 'cluster-stopped'
    $before = Read-ComputeSnapshot $clusterRead
    Assert-R2Profiles $before $entry.beforeProfiles $entry.beforeStates
    if ($entry.healthProfile -ceq 'strict') {
        Assert-ComputeEqual $before.clusterStatic $plan.baseline.clusterStatic 'Strict cluster identities differ'
        $h = $before.clusterHealth
        Assert-Compute ($h.allNodesUp -and $h.allCsvOnline -and $h.allMirrorsHealthy -and $h.poolHealthy -and $h.activeStorageJobs.Count -eq 0 -and $h.quorumType -ceq 'Majority' -and $null -eq $h.witness) 'All Healthy/OK and no jobs required before next outage'
    } elseif ($entry.healthProfile -ceq 'selected-maintenance') {
        $proof = Get-Content (Join-Path $root ('drain-proof-' + $entry.node + '.json')) -Raw | ConvertFrom-Json
        Assert-ComputeMaintenanceHealth $before $entry.node $proof ($entry.effect -ceq 'resume')
    }
    if ((Get-VMHost).LogicalProcessorCount -ne $entry.expectedHostLogicalProcessors) { throw 'Actual host size/topology gate differs' }
    foreach ($volume in $before.volumes) {
        $budget = $plan.admission.volumeBudgets.PSObject.Properties[$volume.letter].Value
        Assert-Compute ($volume.health -ceq 'Healthy' -and $volume.free -ge $budget.freeFloorBytes -and ($budget.maximumVhdBytes + $budget.runtimeBytes + $budget.metadataBytes + $budget.freeFloorBytes) -le $volume.size) 'Runtime-state/free volume admission failed'
    }
    if ($entry.effect -cin @('cluster-stop', 'drain', 'resume')) {
        $target = if ($entry.node) { $entry.node } else { 'LB-NODE01' }
        $session = New-ComputeSession $target
    }
    $state.rpcInvoked = $true; Save-R2Worker 'rpc-pending'
    try {
        switch -CaseSensitive ($entry.effect) {
            'cluster-stop' {
                Invoke-Command -Session $session -ErrorAction Stop -ScriptBlock {
                    # Force suppresses confirmation only. Wait 0 returns after initiating.
                    Stop-Cluster -Cluster smal-localbox01 -Force -Wait 0 -ErrorAction Stop
                } | Out-Null
            }
            'guest-stop' {
                $vm = Get-VM -Id $plan.guestIds.PSObject.Properties[$entry.guest].Value
                if ($vm.Name -cne $entry.guest -or $vm.State.ToString() -cne 'Running') { throw 'Exact Running guest required' }
                Stop-VM -VM $vm -Confirm:$false -ErrorAction Stop
            }
            'memory' {
                $vm = Get-VM -Id $plan.guestIds.PSObject.Properties[$entry.node].Value
                if ($vm.Name -cne $entry.node -or $vm.State.ToString() -cne 'Off') { throw 'Memory resize requires independently observed Off' }
                Set-VMMemory -VM $vm -StartupBytes 128GB -ErrorAction Stop
            }
            'cpu' {
                $vm = Get-VM -Id $plan.guestIds.PSObject.Properties[$entry.node].Value
                if ($vm.Name -cne $entry.node -or $vm.State.ToString() -cne 'Off') { throw 'CPU resize requires independently observed Off' }
                Set-VMProcessor -VM $vm -Count 16 -ErrorAction Stop
            }
            'drain' {
                Invoke-Command -Session $session -ArgumentList $entry.node -ErrorAction Stop -ScriptBlock { param($node) Suspend-ClusterNode -Cluster smal-localbox01 -Name $node -Drain -ErrorAction Stop | Out-Null }
                $afterDrain = Read-ComputeSnapshot
                $ids = @($plan.transitionContract.deviceOwners.PSObject.Properties | Where-Object Value -CEQ $entry.node | ForEach-Object Name)
                $devices = @($afterDrain.clusterHealth.devices | Where-Object owner -CEQ $entry.node)
                Assert-Compute ($ids.Count -eq 8 -and $devices.Count -eq 8 -and @($devices | Where-Object maintenance -NE $true).Count -eq 0) 'Automatic eight-device maintenance not verified; no node stop permitted'
                $proof = @{ selectedNode = $entry.node; rpcReturned = $true; eightDevicesMaintenanceVerified = $true; deviceIds = $ids; planSha256 = $planSha; sourceCommit = $sourceCommit; key = $effectKey }
                Assert-ComputeMaintenanceHealth $afterDrain $entry.node $proof $false
                $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($proof | ConvertTo-Json -Compress))
                $p = Join-Path $root ('drain-proof-' + $entry.node + '.json')
                $s = [IO.File]::Open($p, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
                try { $s.Write($bytes, 0, $bytes.Length); $s.Flush($true) } finally { $s.Dispose() }
                $state.drainProof = $proof
            }
            'resume' {
                # Do not wait for Healthy or resync before this compensating return to service.
                Invoke-Command -Session $session -ArgumentList $entry.node -ErrorAction Stop -ScriptBlock { param($node) Resume-ClusterNode -Cluster smal-localbox01 -Name $node -Failback NoFailback -ErrorAction Stop | Out-Null }
            }
            'startup-grant' {
                $grant = @{ operationId = $plan.operationId; planSha256 = $planSha; sourceCommit = $sourceCommit; key = $entry.startupKey
                    allPriorRemoteEffectsSettled = $true; expectedHostLogicalProcessors = 64
                    guests = @($before.guestsStatic | ForEach-Object { @{ name = $_.name; id = $_.id; cpu = $_.cpu; memory = $_.memory } }) }
                $grantPath = Join-Path $root 'startup-grant.json'
                if (Test-Path $grantPath) {
                    $old = Get-Content $grantPath -Raw | ConvertFrom-Json
                    if (-not (Test-Path (Join-Path $root ('startup-' + $old.key + '.state.json')))) { throw 'Unconsumed grant exists' }
                    $archive = Join-Path $root ('startup-grant-' + $old.key + '.json')
                    [IO.File]::Move($grantPath, $archive)
                }
                $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($grant | ConvertTo-Json -Depth 10 -Compress))
                $s = [IO.File]::Open($grantPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
                try { $s.Write($bytes, 0, $bytes.Length); $s.Flush($true) } finally { $s.Dispose() }
                $state.remoteGrant = $grant
            }
            default { throw 'Unlisted one-effect stage' }
        }
        $state.outcome = 'rpc-returned-await-independent-observation'
    } finally {
        # Return is not effect convergence. Original intent and PID persist after exceptions.
        Save-R2Worker 'returned'
    }
} catch {
    $state.errorType = $_.Exception.GetType().Name; $state.errorLine = $_.InvocationInfo.ScriptLineNumber
    if (-not $state.rpcInvoked) { $state.outcome = 'precondition-refused-no-rpc'; Save-R2Worker 'returned' }
    else { Save-R2Worker $state.phase }
} finally {
    if ($session) { Remove-PSSession $session }
    if ($held) { $mutex.ReleaseMutex() }; $mutex.Dispose()
}
