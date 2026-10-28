$ErrorActionPreference = 'Stop'
$root = 'C:\ProgramData\AzureLocalBox\Bootstrap\storage-20261028-01'
$taskName = 'LocalBox-Storage-20261028-01'
$task = Get-ScheduledTask -TaskName $taskName
$info = Get-ScheduledTaskInfo -TaskName $taskName
$s = Get-Content (Join-Path $root 'state.json') -Raw | ConvertFrom-Json
$heartbeat = if (Test-Path (Join-Path $root 'heartbeat.json')) { Get-Content (Join-Path $root 'heartbeat.json') -Raw | ConvertFrom-Json } else { $null }
$volume = Get-Volume -DriveLetter V -ErrorAction SilentlyContinue
@{ atUtc = (Get-Date).ToUniversalTime().ToString('o'); runId = $s.runId; scope = $s.scope; status = $s.status; phase = $s.phase; errorType = $s.errorType; taskState = $task.State.ToString(); lastTaskResult = $info.LastTaskResult; lastUpdatedAtUtc = $s.lastUpdatedAtUtc; heartbeatUtc = $(if ($heartbeat) { $heartbeat.atUtc } else { $null }); osDiskAndPartitionUnchanged = $s.osDiskAndPartitionUnchanged; volume = $(if ($volume) { @{ letter = 'V'; fileSystem = $volume.FileSystem; sizeBytes = $volume.Size; health = $volume.HealthStatus.ToString() } } else { $null }); clusterBootstrapComplete = $false } | ConvertTo-Json -Depth 5 -Compress
