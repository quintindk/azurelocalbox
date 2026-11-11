# New-phase synchronous single-effect runtime. No detached worker or old GO/root writes.
function Assert-DayAuthority {
    $now=[DateTimeOffset]::UtcNow
    Assert-Compute ($plan.operationId -ceq 'smal-foundation-profile-20261111-02' -and $plan.root -ceq 'C:\ProgramData\AzureLocalBox\FoundationProfile-20261111-02' -and $plan.maximumExecutionDeadline -ceq '2026-11-11T15:20:00+02:00' -and $plan.executionApproval.parentGo -eq $true -and $plan.nativeEffectsApproved -eq $true -and $plan.postNightlyProtectionProjection.acceptedByParent -eq $true) 'Exact approved new-day phase/current posture required; old03/04 approval is not renewed'
    Assert-Compute ($now -lt [DateTimeOffset]::Parse($plan.executionApproval.expiresAt) -and [DateTimeOffset]::Parse($plan.executionApproval.expiresAt) -le [DateTimeOffset]::Parse($plan.maximumExecutionDeadline)) 'New-day GO expired/exceeds cutoff'
    $at=[DateTimeOffset]::Parse($proof.entitlement.observedAtUtc)
    Assert-Compute ($at -le $now -and ($now-$at).TotalSeconds -le 300 -and $proof.entitlement.currentEffectiveOwnerVerified -eq $true -and [DateTimeOffset]::Parse($proof.entitlement.earliestOwnerExpiry) -ge [DateTimeOffset]::Parse($plan.executionApproval.expiresAt)) 'Actual new effective-Owner read stale/missing/short'
    Assert-Compute ($plan.writerLaneHandoff.acceptedByParent -eq $true -and $plan.writerLaneHandoff.previousWriterExited -eq $true -and $plan.writerLaneHandoff.moc3Observed -eq $true -and $plan.writerLaneHandoff.actualMoc3ObserveReceiptSha256 -cmatch '^[a-f0-9]{64}$' -and $plan.writerLaneHandoff.previousWriterExitReceiptSha256 -cmatch '^[a-f0-9]{64}$') 'Exclusive hardware lane has not transferred after actual MOC3/known writer exit'
}
function Assert-DayMoc($read,[string[]]$expected,[string]$peer,$snapshot){
    Assert-Compute ($read.qualified -eq $true -and $read.membershipObserved -eq $true -and $read.observerNode -ceq $peer -and $snapshot.states[$peer] -ceq 'Running') 'Qualified exact current peer/MOC reader required'
    Assert-ComputeEqual $read.commands $plan.mocContract.nodes.PSObject.Properties[$peer].Value.commands 'Installed MOC source/signature differs'
    $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach($member in @($read.members)){$n=$member;if($n -is [Management.Automation.PSObject]){$n=$n.PSObject.BaseObject};Assert-Compute ($n -is [string] -and $n -cin @('LB-NODE01','LB-NODE02','LB-NODE03') -and $seen.Add([string]$n)) 'Canonical native MOC strings only; no value/Value conversion'}
    Assert-Compute ($seen.Count -eq $expected.Count) 'MOC membership count differs'
    foreach($n in $expected){Assert-Compute ($seen.Contains($n)) 'Exact expected MOC member missing'}
    Assert-Compute (@($snapshot.clusterHealth.nodeStates|Where-Object {$_.name -ceq $peer -and $_.state -ceq 'Up'}).Count -eq 1) 'MOC executing peer not currently Up'
}
function Assert-DayProfiles($snapshot,$row){
    foreach($k in @('hostStatic','volumesStatic','clusterStatic')){Assert-ComputeEqual $snapshot[$k] $plan.baseline.PSObject.Properties[$k].Value ('Accepted new-phase static drift: '+$k)}
    Assert-Compute (@($snapshot.guestsStatic).Count -eq 4) 'Four original VMs required'
    foreach($g in $snapshot.guestsStatic){
        $old=@($plan.baseline.guestsStatic|Where-Object name -CEQ $g.name);$p=$row.beforeProfiles.PSObject.Properties[$g.name].Value
        Assert-Compute ($old.Count -eq 1 -and $null -ne $p -and $g.cpu -eq $p.cpu -and $g.memory -eq $p.memory -and $snapshot.states[$g.name] -ceq $row.beforeStates.PSObject.Properties[$g.name].Value) 'Exact selected profiles/power differ'
        foreach($key in @(Get-ComputeKeys $old[0])){
            if($key -cin @('cpu','memory')){continue}
            if($key -ceq 'protectorHash' -and $g.protectorHash -cne $old[0].protectorHash){
                $accepted=$proof.acceptedCurrentProtectionProjection
                Assert-Compute ($accepted.acceptedByParent -eq $true -and $accepted.operationId -ceq $plan.operationId -and $accepted.actualObserveReceiptSha256 -cmatch '^[a-f0-9]{64}$' -and [DateTimeOffset]::UtcNow -lt [DateTimeOffset]::Parse($accepted.expiresAtUtc) -and [DateTimeOffset]::Parse($accepted.expiresAtUtc) -le [DateTimeOffset]::Parse($plan.maximumExecutionDeadline) -and $accepted.expectedProtectorFingerprints.PSObject.Properties[$g.name].Value -ceq $g.protectorHash) 'Opaque protection transition unbound: retain raw hash, require actual parent-accepted current posture'
            }else{Assert-ComputeEqual (Get-ComputeField $g $key) (Get-ComputeField $old[0] $key) ('Actual non-profile drift: '+$g.name+'.'+$key)}
        }
        $vm=Get-VM -Id $g.id;$security=Get-VMSecurity -VM $vm;$firmware=Get-VMFirmware -VM $vm
        $current=@{name=$g.name;id=$g.id;tpmEnabled=$security.TpmEnabled;shielded=$security.Shielded;encryptStateAndVmMigrationTraffic=$security.EncryptStateAndVmMigrationTraffic;bindToHostTpm=$security.BindToHostTpm;virtualizationBasedSecurityOptOut=$security.VirtualizationBasedSecurityOptOut;secureBoot=$firmware.SecureBoot.ToString();secureBootTemplate=$firmware.SecureBootTemplate;secureBootTemplateId=$firmware.SecureBootTemplateId.ToString()}
        $expected=@($plan.expectedPublicProtection.guests|Where-Object name -CEQ $g.name)
        Assert-Compute ($expected.Count -eq 1) 'Current accepted typed VM public protection missing'
        Assert-ComputeEqual $current $expected[0] 'Actual typed security/TPM/SecureBoot posture differs from explicit new-phase projection'
    }
    $getter=@(Get-Command Get-HgsGuardian -All -ErrorAction Stop);$binding=$plan.expectedPublicProtection.command
    Assert-Compute ($getter.Count -eq 1 -and $getter[0].ModuleName -ceq $binding.moduleName -and $getter[0].Module.Version.ToString() -ceq $binding.moduleVersion -and (Get-FileHash $getter[0].Module.Path).Hash.ToLowerInvariant() -ceq $binding.moduleSha256) 'Current public HGS getter source/signature differs from accepted posture'
    $guardian=& $getter[0] -Name $plan.expectedPublicProtection.guardianName -ErrorAction Stop
    foreach($expected in @($plan.expectedPublicProtection.publicCertificates)){$cert=$guardian.PSObject.Properties[$expected.property].Value;Assert-Compute ($cert.Thumbprint -ceq $expected.thumbprint -and $cert.NotBefore.ToUniversalTime() -le [datetime]::UtcNow -and [datetime]::UtcNow -le $cert.NotAfter.ToUniversalTime()) 'Actual guardian public certificate/posture changed; no rekey authority'}
    $c=$snapshot.hostCapacity
    Assert-Compute ($c.logicalProcessors -eq 64 -and $c.physicalCores -eq 32 -and $c.memoryBytes -ge 500GB -and $c.freeMemoryBytes -ge 32GB -and (Get-VMHost).NumaSpanningEnabled) 'E64/NUMA/outer memory reserve failed'
    foreach($v in $snapshot.volumes){$b=$plan.admission.volumeBudgets.PSObject.Properties[$v.letter].Value;Assert-Compute ($null -ne $b -and $v.health -ceq 'Healthy' -and $v.free -ge $b.freeFloorBytes -and $b.maximumVhdBytes+$b.runtimeBytes+$b.metadataBytes+$b.freeFloorBytes -le $v.size) 'Unchanged volume/runtime reserve failed'}
    $placements=@($snapshot.nodeCapacity.Values|ForEach-Object {$_.bridgePlacement}|Where-Object id -IEQ '4c6ca5cc-8c9a-499b-8ffe-c029bbfd3522')
    Assert-Compute ($placements.Count -eq 1 -and $placements[0].state -ceq 'Running') 'Protected existing infrastructure VM is not Running exactly once; no other-VM power authority'
    if($row.node -ceq 'LB-NODE01' -and $row.effect -cnotin @('drain','infrastructure-return','complete')){
        $owner=$placements[0].hciNode
        Assert-Compute ($owner -cin @('LB-NODE02','LB-NODE03') -and $snapshot.states[$owner] -ceq 'Running' -and @($snapshot.guestsStatic|Where-Object {$_.name -ceq $owner -and $_.cpu -eq 20 -and $_.memory -eq 96GB}).Count -eq 1) 'Infrastructure must be on an admitted expanded survivor throughout NODE01 outage'
    }
}
function Assert-QualifiedMirrorJobs($h,[bool]$compensating=$false){
    $known=@{'D82EEC019A25474789543A1796B552BB'='UserStorage_1';'97F0D5071BB7314E9F51102237F77085'='ClusterPerformanceHistory';'4C06845FA8C574499A937BD3EB57736A'='UserStorage_2';'7C7DA96B2870124CADF176559F3F64F7'='UserStorage_3';'9E5467C0BAC8834987723430C063E2C3'='Infrastructure_1'}
    $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach($j in @($h.activeStorageJobs)){
        $ids=@($j.affectedVirtualDiskIds)
        Assert-Compute ($ids.Count -eq 1 -and $known.ContainsKey($ids[0]) -and $j.poolId -ceq $plan.baseline.clusterStatic.poolId -and $j.name -cin @(($known[$ids[0]]+'-Repair'),($known[$ids[0]]+'-Regeneration')) -and $seen.Add(($ids[0]+'|'+$j.name))) 'Unknown/foreign/duplicate whole-mirror (VD,name) tuple'
        if($compensating){Assert-Compute ($j.state -cin @('New','Running','Suspended')) 'Unknown limited-return job state'}else{Assert-Compute ($j.state -ceq 'Suspended') 'Further offline configuration permits only exact suspended jobs'}
        foreach($id in @($j.affectedDeviceIds)){Assert-Compute ($null -eq $id -or ($id -is [string] -and $id -cin @($plan.transitionContract.deviceOwners.PSObject.Properties.Name))) 'Foreign reported physical device; null remains null'}
    }
    Assert-Compute ($h.physicalFreeBytes -ge $plan.admission.requiredPhysicalFreeBytes+$plan.admission.repairReserveBytes) 'Unchanged physical repair reserve failed'
}
function Assert-DayHealth($snapshot,$row){
    $h=$snapshot.clusterHealth
    if($row.healthProfile -ceq 'strict'){
        Assert-Compute ($h.allNodesUp -and $h.allCsvOnline -and $h.allMirrorsHealthy -and $h.poolHealthy -and @($h.activeStorageJobs).Count -eq 0 -and $h.quorumType -ceq 'Majority' -and $null -eq $h.witness -and @($h.devices).Count -eq 24 -and @($h.devices|Where-Object {$_.health -cne 'Healthy' -or ($_.operational-join '|') -cne 'OK' -or $_.maintenance}).Count -eq 0) 'Full current all-Up/Healthy/zero-jobs convergence required before next outage/completion'
        Assert-QualifiedMirrorJobs $h $false
    }else{
        if($snapshot.states[$row.node] -ceq 'Off' -and $row.effect -cin @('cpu','memory','guest-start')){$state.offHistoricalQualification=Assert-FutureLimitedOffHealth $snapshot $row.node $proof.drainProof ($row.effect -ceq 'guest-start')}
        else{Assert-ComputeMaintenanceHealth $snapshot $row.node $proof.drainProof ($row.effect -cin @('resume','moc-add'))}
    }
}
function Save-R2Worker([string]$phase){
    $state.sequence++;$state.phase=$phase;$state.atUtc=[datetime]::UtcNow.ToString('o')
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($state|ConvertTo-Json -Depth 30 -Compress))
    $event=Join-Path $root ('worker-'+$stage+'-event-'+$state.sequence+'.json')
    $f=[IO.File]::Open($event,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read);try{$f.Write($bytes,0,$bytes.Length);$f.Flush($true)}finally{$f.Dispose()}
    $tmp=$statePath+'.sequence-'+$state.sequence+'.tmp';$f=[IO.File]::Open($tmp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read);try{$f.Write($bytes,0,$bytes.Length);$f.Flush($true)}finally{$f.Dispose()}
    if(Test-Path -LiteralPath $statePath){$backup=$statePath+'.before-sequence-'+$state.sequence+'.json';if(Test-Path $backup){throw 'Backup exists; no overwrite'};[IO.File]::Replace($tmp,$statePath,$backup)}else{[IO.File]::Move($tmp,$statePath)}
}
function New-DayJson([string]$path,$object){
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($object|ConvertTo-Json -Depth 40 -Compress))
    $f=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read);try{$f.Write($bytes,0,$bytes.Length);$f.Flush($true)}finally{$f.Dispose()}
}
function Invoke-DayEffect {
    Assert-DayAuthority
    Assert-Compute ($entry.node -cne 'LB-NODE02' -and -not ($entry.effect -ceq 'memory' -and $entry.node -ceq 'LB-NODE01')) 'NODE02 replay/NODE01 RAM write forbidden'
    $mutex=[Threading.Mutex]::new($false,'Global\AzureLocalBoxComputeCapacityR2');$held=$false;$session=$null
    try{
        $held=$mutex.WaitOne(0);Assert-Compute $held 'Existing hardware writer still active'
        if(-not(Test-Path $root)){$null=New-Item $root -ItemType Directory;Set-Acl $root (Get-Acl 'C:\ProgramData\AzureLocalBox\Bootstrap\cluster-prereqs-20261028-01');New-DayJson (Join-Path $root 'operation.json') @{operationId=$plan.operationId;planSha256=$planSha;sourceCommit=$sourceCommit;active=$true}}
        $operation=Get-Content (Join-Path $root 'operation.json') -Raw|ConvertFrom-Json
        Assert-Compute ($operation.operationId -ceq $plan.operationId -and $operation.planSha256 -ceq $planSha -and $operation.sourceCommit -ceq $sourceCommit -and $operation.active -eq $true) 'Existing new-phase operation differs; never reset'
        Assert-Compute (-not(Test-Path $statePath) -and -not(Test-Path (Join-Path $root ('request-'+$stage+'.json')))) 'Original stage already has intent/history; inspect, never replay/rekey'
        $bodyPath=Join-Path $root ('worker-'+$stage+'.scriptblock.ps1')
        $bodyBytes=[Text.Encoding]::UTF8.GetBytes($global:DayExecutingScriptBlockText)
        Assert-Compute ((Get-FutureSha256 $bodyBytes) -ceq $executingSourceSha256) 'Persisted actual ScriptBlock bytes differ from executing self hash'
        $f=[IO.File]::Open($bodyPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read);try{$f.Write($bodyBytes,0,$bodyBytes.Length);$f.Flush($true)}finally{$f.Dispose()}
        foreach($file in @(Get-ChildItem $root -Filter 'worker-*.state.json')){$s=Get-Content $file.FullName -Raw|ConvertFrom-Json;$p=Get-Process -Id $s.pid -ErrorAction SilentlyContinue;Assert-Compute ($s.phase -ceq 'returned' -and $s.rpcReturned -eq $true -and -not($p -and $p.StartTime.ToUniversalTime().ToString('o') -ceq $s.processStartedUtc)) 'Existing phase process/RPC is unresolved'}
        if($entry.previousStage){$p=Get-Content (Join-Path $root ('worker-'+$entry.previousStage+'.state.json')) -Raw|ConvertFrom-Json;Assert-Compute ($p.phase -ceq 'returned' -and $p.rpcReturned -eq $true -and $p.sourceSha256 -ceq $proof.acceptedPreviousWorkerScriptBlockSha256 -and $proof.acceptedPreviousObserveReceiptSha256 -cmatch '^[a-f0-9]{64}$') 'Exact preceding effect independent observation/source missing'}
        if($null -ne $proof.drainProof -and $entry.effect -cnotin @('infrastructure-return','complete')){Assert-Compute ($proof.drainProof.selectedNode -ceq $entry.node) 'Do not carry previous node drain into another outage';$path=Join-Path $root ('drain-proof-'+$entry.node+'.json');if(-not(Test-Path $path)){New-DayJson $path $proof.drainProof}else{Assert-ComputeEqual (Get-Content $path -Raw|ConvertFrom-Json) $proof.drainProof 'Original actual drain proof changed'}}
        New-DayJson (Join-Path $root ('request-'+$stage+'.json')) @{operationId=$plan.operationId;planSha256=$planSha;sourceCommit=$sourceCommit;stage=$stage;key=$effectKey;workerScriptBlockSha256=$executingSourceSha256}
        $state=@{operationId=$plan.operationId;planSha256=$planSha;sourceCommit=$sourceCommit;stage=$stage;key=$effectKey;pid=$PID;processStartedUtc=(Get-Process -Id $PID).StartTime.ToUniversalTime().ToString('o');sourceSha256=$executingSourceSha256;sequence=0;rpcInvoked=$false;rpcReturned=$false;outcome='unknown';futureIdentityBindingSha256=$futureIdentityBindingSha256;futureIdentityFactoryContractSha256=$factoryContractSha256;futureMapTransportReceiptSha256=$futureAcceptance.transportReceiptSha256;sourceCommitSemantics='New-phase factory publication, not old03 anchor or outer transport wrapper hash'}
        Save-R2Worker 'preflight'
        $before=Read-ComputeSnapshot $true
        Assert-DayProfiles $before $entry;Assert-DayHealth $before $entry
        $peer=if($entry.node -ceq 'LB-NODE01'){'LB-NODE02'}else{'LB-NODE01'}
        $moc=Read-ProfileMoc $peer;Assert-DayMoc $moc $entry.beforeMocMembers $peer $before
        if($entry.effect -ceq 'drain'){Assert-FutureFreshBeforeDrain $futureMap ([DateTimeOffset]::UtcNow)}
        Assert-DayAuthority
        $state.rpcInvoked=$true;Save-R2Worker 'rpc-pending'
        switch -CaseSensitive ($entry.effect){
            'drain'{
                if($entry.node -ceq 'LB-NODE01'){foreach($n in @('LB-NODE02','LB-NODE03')){Assert-Compute ($before.states[$n] -ceq 'Running' -and @($before.guestsStatic|Where-Object {$_.name -ceq $n -and $_.cpu -eq 20 -and $_.memory -eq 96GB}).Count -eq 1) 'Expanded survivors required before NODE01 drain'}}
                $session=New-ComputeSession $entry.node
                Invoke-Command -Session $session -ArgumentList $entry.node -ErrorAction Stop -ScriptBlock {param($n) Suspend-ClusterNode -Cluster smal-localbox01 -Name $n -Drain -ErrorAction Stop|Out-Null}
            }
            {$_ -cin @('moc-remove','moc-add')}{
                if($entry.effect -ceq 'moc-add'){Assert-Compute (@($before.clusterHealth.nodeStates|Where-Object {$_.name -ceq $entry.node -and $_.state -ceq 'Up'}).Count -eq 1) 'MOC add requires current selected Up'}
                $session=New-ComputeSession $peer
                Invoke-Command -Session $session -ArgumentList $peer,$entry.node,$entry.effect,$plan.mocContract.nodes.PSObject.Properties[$peer].Value -ErrorAction Stop -ScriptBlock {
                    param($peer,$target,$effect,$binding)
                    $ErrorActionPreference='Stop';$admin=Get-LocalUser ASBuiltInAdmin
                    if($env:COMPUTERNAME -cne $peer -or $peer -ceq $target -or -not $admin.Enabled -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne $admin.SID.Value){throw 'Exact healthy-peer/RID500 caller differs'}
                    $name=if($effect -ceq 'moc-remove'){'Remove-MocPhysicalNode'}else{'New-MocPhysicalNode'};$cmd=@(Get-Command $name -All)
                    $expected=$binding.commands.PSObject.Properties[$name].Value
                    if($cmd.Count -ne 1 -or $cmd[0].ModuleName -cne $expected.moduleName -or $cmd[0].Module.Version.ToString() -cne $expected.moduleVersion -or (Get-FileHash $cmd[0].Module.Path).Hash.ToLowerInvariant() -cne $expected.moduleSha256){throw 'Installed exact MOC command/source changed'}
                    & $cmd[0] -NodeName $target -ErrorAction Stop|Out-Null
                }
            }
            'guest-stop'{
                Assert-Compute (@($before.clusterHealth.nodeStates|Where-Object {$_.name -ceq $entry.node -and $_.state -ceq 'Paused'}).Count -eq 1) 'Current selected Paused required'
                $state.futurePreStopMaintenanceEvidence=New-FuturePreStopMaintenanceEvidence $before;Save-R2Worker 'pre-stop-maintenance-read-verified'
                $vm=Get-VM -Id $plan.guestIds.PSObject.Properties[$entry.node].Value
                Assert-Compute ($vm.Name -ceq $entry.node -and $vm.State.ToString() -ceq 'Running') 'Exact current Running selected guest required'
                Stop-VM -VM $vm -Confirm:$false -ErrorAction Stop
            }
            'cpu'{
                $vm=Get-VM -Id $plan.guestIds.PSObject.Properties[$entry.node].Value;$p=Get-VMProcessor -VM $vm
                Assert-Compute ($vm.Name -ceq $entry.node -and $vm.State.ToString() -ceq 'Off' -and $p.ExposeVirtualizationExtensions -and $p.MaximumCountPerNumaNode -ge $entry.targetCpu) 'Exact Off selected supported CPU target required'
                Set-VMProcessor -VM $vm -Count $entry.targetCpu -ErrorAction Stop
            }
            'memory'{
                Assert-Compute ($entry.node -ceq 'LB-NODE03' -and $entry.targetMemoryBytes -eq 96GB) 'Only NODE03 RAM96 write exists'
                $vm=Get-VM -Id $plan.guestIds.'LB-NODE03';$m=Get-VMMemory -VM $vm
                Assert-Compute ($vm.Name -ceq 'LB-NODE03' -and $vm.State.ToString() -ceq 'Off' -and -not $m.DynamicMemoryEnabled -and $m.Minimum -le 96GB -and $m.Maximum -ge 96GB) 'Native memory bounds/Off state differ'
                Set-VMMemory -VM $vm -StartupBytes 96GB -ErrorAction Stop
            }
            'guest-start'{
                $vm=Get-VM -Id $plan.guestIds.PSObject.Properties[$entry.node].Value
                Assert-Compute ($vm.Name -ceq $entry.node -and $vm.State.ToString() -ceq 'Off' -and $vm.ProcessorCount -eq $entry.targetCpu -and $vm.MemoryStartup -eq $entry.targetMemoryBytes -and $before.hostCapacity.freeMemoryBytes -ge $entry.targetMemoryBytes+32GB) 'Exact current resized Off guest/start reserve required'
                Start-VM -VM $vm -ErrorAction Stop
            }
            'resume'{
                $session=New-ComputeSession $entry.node
                Invoke-Command -Session $session -ArgumentList $entry.node -ErrorAction Stop -ScriptBlock {param($n) Resume-ClusterNode -Cluster smal-localbox01 -Name $n -Failback NoFailback -ErrorAction Stop|Out-Null}
            }
            'infrastructure-return'{
                $session=New-ComputeSession 'LB-NODE01'
                Invoke-Command -Session $session -ErrorAction Stop -ScriptBlock {Move-ClusterVirtualMachineRole -Cluster smal-localbox01 -VMId '4c6ca5cc-8c9a-499b-8ffe-c029bbfd3522' -Node LB-NODE01 -MigrationType Live -ErrorAction Stop|Out-Null}
            }
            'complete'{
                $placements=@($before.nodeCapacity.Values|ForEach-Object {$_.bridgePlacement}|Where-Object id -IEQ '4c6ca5cc-8c9a-499b-8ffe-c029bbfd3522')
                Assert-Compute ($placements.Count -eq 1 -and $placements[0].state -ceq 'Running' -and $placements[0].hciNode -ceq 'LB-NODE01') 'Actual infrastructure VM not Running back on NODE01'
                New-DayJson (Join-Path $root 'completion.json') @{planSha256=$planSha;sourceCommit=$sourceCommit;allUpHealthyZeroJobs=$true;infrastructureRunningOnNode01=$true;finalProfiles=$entry.beforeProfiles;observedAtUtc=$before.atUtc}
                $operation.active=$false;$opPath=Join-Path $root 'operation.json';$tmp=$opPath+'.completion.tmp';$backup=$opPath+'.before-completion.json'
                Assert-Compute (-not(Test-Path $backup)) 'New-phase completion backup already exists; no overwrite'
                New-DayJson $tmp $operation;[IO.File]::Replace($tmp,$opPath,$backup)
            }
            default{throw 'Effect outside original two-node continuation'}
        }
        $state.rpcReturned=$true;$state.outcome='rpc-returned-await-independent-observation';Save-R2Worker 'returned'
        return @{status='synchronous-effect-returned-not-independent-settlement';operationId=$plan.operationId;planSha256=$planSha;stage=$stage;worker=$state;workerScriptBlockSha256=$executingSourceSha256;nativeAfterReadPerformed=$false;atUtc=[datetime]::UtcNow.ToString('o')}
    }catch{if($null -ne $state){$state.errorType=$_.Exception.GetType().Name;Save-R2Worker $(if($state.rpcInvoked){'rpc-uncertain'}else{'returned'})};throw}
    finally{if($session){Remove-PSSession $session};if($held){$mutex.ReleaseMutex()};$mutex.Dispose()}
}
