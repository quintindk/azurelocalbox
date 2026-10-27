# Read-only reconciliation of the rejected setup. Never reads a private key.
$ErrorActionPreference = 'Stop'
$dir = 'C:\ProgramData\ssh'
$config = Join-Path $dir 'sshd_config'
$rows = @(foreach ($line in (Get-Content $config)) {
    $normalised = ($line.Trim() -replace '\s+', ' ')
    if (-not $normalised -or $normalised.StartsWith('#')) { continue }
    $parts = $normalised -split ' ', 2
    $safe = $normalised -match '^(PasswordAuthentication|PubkeyAuthentication|AllowTcpForwarding|AllowAgentForwarding) (yes|no)$' -or
        $normalised -match '^Port [0-9]+$' -or
        $normalised -match '^AuthorizedKeysFile (\.ssh/authorized_keys|__PROGRAMDATA__/ssh/administrators_authorized_keys)$' -or
        $normalised -match '^Match Group administrators$' -or
        $normalised -match '^Subsystem sftp ([a-zA-Z]:[\\/][a-zA-Z0-9\\/._-]+|sftp-server.exe)$' -or
        $normalised -match '^AllowUsers [a-zA-Z0-9_-]+$'
    @{ directive = $parts[0]; value = $(if ($safe) { $normalised } else { 'custom-value-redacted' }) }
})
[ordered]@{
    computer = $env:COMPUTERNAME
    atUtc = (Get-Date).ToUniversalTime().ToString('o')
    configSha256 = (Get-FileHash $config -Algorithm SHA256).Hash
    activeConfiguration = $rows
    setupMarkerExists = Test-Path (Join-Path $dir 'localbox-private-ssh.json')
    backupExists = Test-Path (Join-Path $dir 'sshd_config.before-localbox-private-ssh')
    adminKeysExist = Test-Path (Join-Path $dir 'administrators_authorized_keys')
    service = (Get-Service sshd).Status.ToString()
    readOnly = $true
} | ConvertTo-Json -Depth 5 -Compress
