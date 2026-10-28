$ErrorActionPreference = 'Stop'
$root = 'C:\ProgramData\AzureLocalBox\Bootstrap\guest-inputs-20261028-02'
$task = Get-ScheduledTask -TaskName 'LocalBox-GuestInputs-20261028-02' -ErrorAction SilentlyContinue
if (-not (Test-Path $root)) { @{ directoryExists = $false; taskExists = [bool]$task } | ConvertTo-Json -Compress; exit 0 }
$state = Get-Content (Join-Path $root 'state.json') -Raw | ConvertFrom-Json
$info = if ($task) { Get-ScheduledTaskInfo -TaskName $task.TaskName } else { $null }
@{ atUtc = (Get-Date).ToUniversalTime().ToString('o'); state = $state; taskExists = [bool]$task; taskState = $(if ($task) { $task.State.ToString() } else { $null }); lastTaskResult = $info.LastTaskResult; manifestSha256 = (Get-FileHash (Join-Path $root 'manifest.json')).Hash; workerSha256 = (Get-FileHash (Join-Path $root 'worker.ps1')).Hash; actualTriggerCount = @($task.Triggers | Where-Object { $null -ne $_ }).Count; clusterBootstrapComplete = $false } | ConvertTo-Json -Depth 12 -Compress
