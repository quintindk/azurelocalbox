function Assert-QualifiedMirrorJobs($h, [bool]$compensating = $false) {
    # Exact whole-mirror association. Null device IDs are not physical attribution.
    $known = @{
        'D82EEC019A25474789543A1796B552BB' = 'UserStorage_1-Repair'
        '97F0D5071BB7314E9F51102237F77085' = 'ClusterPerformanceHistory-Repair'
        '4C06845FA8C574499A937BD3EB57736A' = 'UserStorage_2-Repair'
        '7C7DA96B2870124CADF176559F3F64F7' = 'UserStorage_3-Repair'
        '9E5467C0BAC8834987723430C063E2C3' = 'Infrastructure_1-Repair'
    }
    Assert-Compute ($plan.operationId -ceq 'smal-foundation-profile-20261110-02' -and $plan.maximumExecutionDeadline -ceq '2026-11-10T20:00:00+02:00' -and $plan.baseline.clusterStatic.poolId -ceq '{923c0194-3ed4-449a-ae14-0f62861e0ec8}') 'Different maintenance qualification operation/pool/bound'
    $seen = @{}
    foreach ($job in @($h.activeStorageJobs)) {
        $ids = @($job.affectedVirtualDiskIds)
        Assert-Compute ($ids.Count -eq 1 -and $ids[0] -is [string] -and $known.ContainsKey($ids[0]) -and $job.name -ceq $known[$ids[0]] -and $job.poolId -ceq $plan.baseline.clusterStatic.poolId) 'Repair is not an exact known same-pool whole mirror/name'
        Assert-Compute (-not $seen.ContainsKey($ids[0])) 'Duplicate whole-mirror repair association'
        $seen[$ids[0]] = $true
        if ($compensating) {
            Assert-Compute ($job.state -cin @('Suspended', 'Running')) 'Unknown compensating whole-mirror repair state'
        } else {
            Assert-Compute ($job.state -ceq 'Suspended') 'Further offline/resize allows only suspended exact mirror repairs'
        }
        foreach ($id in @($job.affectedDeviceIds)) {
            if ($null -eq $id) { continue }
            Assert-Compute ($id -is [string] -and $id -cin @($plan.transitionContract.deviceOwners.PSObject.Properties.Name)) 'Reported repair device is outside exact existing 24'
        }
    }
    Assert-Compute ($h.physicalFreeBytes -ge ($plan.admission.requiredPhysicalFreeBytes + $plan.admission.repairReserveBytes)) 'Maintenance physical headroom insufficient'
}
