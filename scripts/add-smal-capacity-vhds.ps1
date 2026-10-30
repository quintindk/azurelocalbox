__CAPACITY_PRELUDE__
# Only new files and free SCSI slots. Never resize/format a pooled guest disk.
Assert-CapacityHost
$original = @(Read-CapacityOriginalVhds); $null = Read-CapacityClusterBaseline
$before = Get-Content (Join-Path $capacityRoot 'baseline.json') -Raw | ConvertFrom-Json
$formatted = Get-Content (Join-Path $capacityRoot 'format.json') -Raw | ConvertFrom-Json
$x = Get-Volume -DriveLetter X; $dataRoot = 'X:\AzureLocalBox\CapacityExpansion-20261030-01'
if ($formatted.status -cne 'complete-new-only-4tib-x-volume' -or $formatted.azureDiskUniqueId -ine $context.azureDiskUniqueId -or $x.UniqueId -cne $formatted.volumeId -or $x.HealthStatus.ToString() -cne 'Healthy' -or $x.SizeRemaining -lt 2300GB -or (Test-Path $dataRoot)) { throw 'Exact owned new capacity differs or VHD attempt exists' }
$newDisk = Get-Disk -UniqueId $formatted.windowsUniqueId
if ($newDisk.IsBoot -or $newDisk.IsSystem -or $newDisk.Size -ne 4096GB -or $newDisk.PartitionStyle.ToString() -cne 'GPT') { throw 'Exact new backing disk differs' }
$marker = [IO.File]::Open((Join-Path $capacityRoot 'vhds.started'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None); $marker.Dispose()
$path = Join-Path $capacityRoot 'vhds.json'
$record = @{ status = 'creating-owned-new-vhds'; sourceCommit = $sourceCommit; planSha256 = $approval.planSha256; azureDiskId = $plan.newDisk.id; azureDiskUniqueId = $context.azureDiskUniqueId; disks = @(); existingVhdResized = $false; csvResized = $false }
try {
    Save-CapacityState $path $record
    $null = New-Item $dataRoot -ItemType Directory
    Set-Acl $dataRoot (Get-Acl 'C:\ProgramData\AzureLocalBox\Bootstrap\cluster-prereqs-20261028-01')
    foreach ($property in $plan.nodes.PSObject.Properties) {
        $name = $property.Name; $node = $property.Value; $directory = Join-Path $dataRoot $name
        $null = New-Item $directory -ItemType Directory
        $prototype = @($original | Where-Object { $_.name -ceq $name -and $_.lun -eq 1 })
        if ($prototype.Count -ne 1 -or $prototype[0].type -cne 'Dynamic') { throw 'Exact existing dynamic data-VHD prototype differs' }
        foreach ($spec in $node.newDisks) {
            if ($spec.path -cne (Join-Path $directory ('S2D-' + $spec.lun + '.vhdx')) -or $spec.lun -notin @(5,6,7,8) -or $spec.sizeBytes -ne 170GB -or (Test-Path $spec.path)) { throw 'Exact new VHD path/LUN/size differs or exists' }
            $record.status = 'one-new-vhd-create-pending'; $record.pendingPath = $spec.path; Save-CapacityState $path $record
            $vhd = New-VHD -Path $spec.path -Dynamic -SizeBytes 170GB -BlockSizeBytes $prototype[0].blockSize -LogicalSectorSizeBytes $prototype[0].logicalSectorSize -PhysicalSectorSizeBytes $prototype[0].physicalSectorSize
            if ($vhd.Size -ne 170GB -or $vhd.ParentPath -or $vhd.Attached -or $vhd.VhdType.ToString() -cne 'Dynamic') { throw 'New owned VHD shape differs' }
            $bytes = $vhd.DiskIdentifier.ToByteArray(); $unique = '60022480' + [BitConverter]::ToString([byte[]]@($bytes[0..5] + $bytes[10..15])).Replace('-','')
            $record.disks += @{ node = $name; vmId = $node.vmId; lun = $spec.lun; path = $vhd.Path; vhdId = $vhd.DiskIdentifier.ToString(); guestUniqueId = $unique; sizeBytes = $vhd.Size; attached = $false }
            $record.Remove('pendingPath'); Save-CapacityState $path $record
        }
    }
    if ($record.disks.Count -ne 12 -or @($record.disks.guestUniqueId | Sort-Object -Unique).Count -ne 12) { throw 'Exactly twelve distinct owned new VHDs required' }
    foreach ($row in $record.disks) {
        $vm = Get-VM -Id $row.vmId
        if ($vm.Name -cne $row.node -or $vm.State.ToString() -cne 'Running' -or @(Get-VMHardDiskDrive -VM $vm | Where-Object { $_.ControllerType.ToString() -eq 'SCSI' -and $_.ControllerNumber -eq 0 -and $_.ControllerLocation -eq $row.lun }).Count -ne 0) { throw 'New SCSI slot is no longer free on the exact running node' }
        $vhd = Get-VHD -Path $row.path
        if ($vhd.DiskIdentifier.ToString() -ine $row.vhdId -or $vhd.Size -ne 170GB -or $vhd.Attached) { throw 'Owned VHD identity differs before attachment' }
        $record.status = 'one-new-vhd-attach-pending'; $record.pendingPath = $row.path; Save-CapacityState $path $record
        Add-VMHardDiskDrive -VM $vm -Path $row.path -ControllerType SCSI -ControllerNumber 0 -ControllerLocation $row.lun
        $actual = @(Get-VMHardDiskDrive -VM $vm | Where-Object { $_.ControllerType.ToString() -eq 'SCSI' -and $_.ControllerNumber -eq 0 -and $_.ControllerLocation -eq $row.lun })
        if ($actual.Count -ne 1 -or $actual[0].Path -ine $row.path) { throw 'Exact new VHD attachment readback differs' }
        $row.attached = $true; $record.Remove('pendingPath'); Save-CapacityState $path $record
    }
    foreach ($row in $original) {
        $vm = Get-VM -Id $row.vmId; $vhd = Get-VHD -Path $row.path
        $actual = @(Get-VMHardDiskDrive -VM $vm | Where-Object ControllerLocation -EQ $row.lun)
        if ($actual.Count -ne 1 -or $actual[0].Path -ine $row.path -or $vhd.DiskIdentifier.ToString() -ine $row.diskId -or $vhd.Size -ne $row.size) { throw 'Original VHD binding changed' }
    }
    Assert-CapacityHost
    $record.status = 'complete-twelve-new-vhds-attached-await-pool-observation'; Save-CapacityState $path $record
} catch { $record.status = 'failed-or-uncertain-inspect-do-not-repeat'; $record.errorType = $_.Exception.GetType().Name; $record.errorLine = $_.InvocationInfo.ScriptLineNumber; Save-CapacityState $path $record }
$record | ConvertTo-Json -Depth 10 -Compress
