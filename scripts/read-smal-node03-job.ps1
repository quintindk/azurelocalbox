# Read-only bounded progress. Never reads a secret, guest answer file or raw setup log.
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -cne 'LocalBox-Client') { throw 'Unexpected host' }
$root = 'C:\ProgramData\AzureLocalBox\Bootstrap\node03-20261029-01'
$task = Get-ScheduledTask -TaskName LocalBox-Node03-20261029-01 -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskName $task.TaskName
$state = Get-Content (Join-Path $root 'state.json') -Raw | ConvertFrom-Json
$heartbeat = if (Test-Path (Join-Path $root 'heartbeat.json')) { Get-Content (Join-Path $root 'heartbeat.json') -Raw | ConvertFrom-Json } else { $null }
@{ atUtc = [datetime]::UtcNow.ToString('o'); taskState = $task.State.ToString(); lastTaskResult = $info.LastTaskResult; heartbeat = $heartbeat; state = $state;
   workerSha256 = (Get-FileHash (Join-Path $root 'worker.ps1')).Hash; bundleSha256 = (Get-FileHash (Join-Path $root 'bundle.json')).Hash;
   actualTriggerCount = @($task.Triggers | Where-Object { $null -ne $_ }).Count; principal = $task.Principal.UserId; registrationInvokedByReader = $false } | ConvertTo-Json -Depth 13 -Compress
