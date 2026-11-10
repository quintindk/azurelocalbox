# R2 dispatch/observe template. No inline multi-effect shutdown or profile mutation.
# Renderer binds public sealed plan, one stage, worker bytes/hash and startup-helper bytes.
$ErrorActionPreference = 'Stop'
$root = 'C:\ProgramData\AzureLocalBox\ComputeCapacity-R2-20261108-01'
if ($env:COMPUTERNAME -cne 'LocalBox-Client' -or $plan.transitionContract.version -ne 2 -or $plan.executionApproval.parentGo -ne $true) { throw 'Exact approved R2 source/plan required' }
$entry = $plan.transitionContract.stages.PSObject.Properties[$stage].Value
if ($null -eq $entry -or $entry.key -cne $effectKey) { throw 'Exact sealed stage/key differs' }
function Read-R2Json([string]$p) { Get-Content -LiteralPath $p -Raw | ConvertFrom-Json }
function New-R2File([string]$path, [byte[]]$bytes) {
    $stream = [IO.File]::Open($path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
}
function Write-R2NewJson([string]$path, $value) { New-R2File $path ([Text.UTF8Encoding]::new($false).GetBytes(($value | ConvertTo-Json -Depth 25 -Compress))) }
function Process-R2Alive($record) {
    if ($null -eq $record -or -not $record.pid -or -not $record.processStartedUtc) { return $null }
    $p = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
    return ($null -ne $p -and $p.StartTime.ToUniversalTime().ToString('o') -ceq $record.processStartedUtc)
}
if ($mode -ceq 'observe') {
    # GET-only: no launch, marker repair, process kill, retry or source installation.
    $request = Read-R2Json (Join-Path $root ('request-' + $stage + '.json'))
    $statePath = Join-Path $root ('worker-' + $stage + '.state.json')
    $worker = if (Test-Path $statePath) { Read-R2Json $statePath } else { $null }
    $workerFile = Join-Path $root ('worker-' + $stage + '.ps1')
    $verified = (Get-FileHash -LiteralPath $workerFile).Hash -ceq $workerSha256
    if ($request.planSha256 -cne $planSha -or $request.key -cne $effectKey -or -not $verified) { throw 'Original request/source identity differs' }
    if ($worker -and ($worker.planSha256 -cne $planSha -or $worker.key -cne $effectKey -or $worker.sourceSha256 -cne $workerSha256)) { throw 'Original worker identity differs' }
    $profiles = @(Get-VM | Sort-Object Name | ForEach-Object { @{ name = $_.Name; id = $_.Id.ToString(); state = $_.State.ToString(); cpu = $_.ProcessorCount; memory = $_.MemoryStartup } })
    $health = $null
    if ($entry.node -and @($profiles | Where-Object { $_.name -cne 'LB-DC01' -and $_.state -ceq 'Running' }).Count -ge 2) {
        $health = Read-ComputeSnapshot
    }
    @{ status = 'complete'; atUtc = [datetime]::UtcNow.ToString('o'); operationId = $plan.operationId; planSha256 = $planSha
       sourceCommit = $sourceCommit; stage = $stage; key = $effectKey; mutationPerformed = $false
       dispatcherAlive = Process-R2Alive $request; workerAlive = Process-R2Alive $worker
       workerIdentityVerified = $null -ne $worker; workerSourceVerified = $verified; worker = $worker
       rpcPhase = $(if ($worker) { $worker.phase } else { 'unknown' }); profiles = $profiles; snapshot = $health
       remoteStartup = @(Get-ChildItem $root -Filter 'startup-*.state.json' -File | ForEach-Object { $s = Read-R2Json $_.FullName; @{ state = $s; alive = Process-R2Alive $s } }) } | ConvertTo-Json -Depth 30 -Compress
} elseif ($mode -ceq 'dispatch') {
    $mutex = [Threading.Mutex]::new($false, 'Global\AzureLocalBoxComputeCapacityR2')
    $held = $false
    try {
        $held = $mutex.WaitOne(0)
        if (-not $held) { throw 'Another remote capacity dispatcher/worker is active' }
        if (Test-Path $root) {
            $operation = Read-R2Json (Join-Path $root 'operation.json')
            if ($operation.planSha256 -cne $planSha -or $operation.sourceCommit -cne $sourceCommit -or $operation.active -ne $true) { throw 'Existing remote operation/source differs' }
            foreach ($file in @(Get-ChildItem $root -Filter 'worker-*.state.json' -File)) {
                $old = Read-R2Json $file.FullName
                if ((Process-R2Alive $old) -ne $false -or $old.phase -cne 'returned') { throw 'Unresolved remote process/RPC blocks every stage' }
            }
            foreach ($file in @(Get-ChildItem $root -Filter 'request-*.json' -File)) {
                $old = Read-R2Json $file.FullName
                $oldWorker = Join-Path $root ('worker-' + $old.stage + '.state.json')
                if (-not (Test-Path $oldWorker)) { throw 'Unresolved launch intent blocks every stage' }
            }
            foreach ($file in @(Get-ChildItem $root -Filter 'startup-*.state.json' -File)) {
                $old = Read-R2Json $file.FullName
                if ((Process-R2Alive $old) -ne $false -or $old.phase -cne 'returned') { throw 'Unresolved canonical startup blocks every stage' }
            }
        } else {
            $null = New-Item $root -ItemType Directory
            Set-Acl $root (Get-Acl 'C:\ProgramData\AzureLocalBox\Bootstrap\cluster-prereqs-20261028-01')
            $helperBytes = [Convert]::FromBase64String($startupHelperBase64)
            New-R2File (Join-Path $root 'startup-interlock.ps1') $helperBytes
            Write-R2NewJson (Join-Path $root 'operation.json') @{ operationId = $plan.operationId; planSha256 = $planSha; sourceCommit = $sourceCommit; active = $true; startupHelperSha256 = $startupHelperSha256 }
        }
        $workerFile = Join-Path $root ('worker-' + $stage + '.ps1')
        $bytes = [Convert]::FromBase64String($workerBase64)
        $hash = [Security.Cryptography.SHA256]::Create()
        try { if ([BitConverter]::ToString($hash.ComputeHash($bytes)).Replace('-', '') -cne $workerSha256) { throw 'Reviewed worker bytes differ' } } finally { $hash.Dispose() }
        New-R2File $workerFile $bytes
        $request = @{ operationId = $plan.operationId; planSha256 = $planSha; sourceCommit = $sourceCommit; stage = $stage; key = $effectKey
            phase = 'launch-pending'; pid = $PID; processStartedUtc = (Get-Process -Id $PID).StartTime.ToUniversalTime().ToString('o') }
        Write-R2NewJson (Join-Path $root ('request-' + $stage + '.json')) $request
        # Detached worker survives SSH termination. Exactly one effect, no timeout extension.
        $p = Start-Process -FilePath powershell.exe -ArgumentList @('-NoLogo', '-NoProfile', '-NonInteractive', '-File', $workerFile) -PassThru -WindowStyle Hidden
        Write-R2NewJson (Join-Path $root ('launch-' + $stage + '-returned.json')) @{ stage = $stage; key = $effectKey; planSha256 = $planSha; pid = $p.Id; phase = 'launch-returned' }
        @{ status = 'complete'; operationId = $plan.operationId; planSha256 = $planSha; sourceCommit = $sourceCommit; stage = $stage; key = $effectKey
            workerPid = $p.Id; launchReturned = $true; effectSettled = $false; closingSshSettlesRpc = $false } | ConvertTo-Json -Compress
    } finally { if ($held) { $mutex.ReleaseMutex() }; $mutex.Dispose() }
} else { throw 'Unknown R2 mode' }
